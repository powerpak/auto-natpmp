#!/usr/bin/env python3

import subprocess
import re
import time
import os
import logging
import argparse
from datetime import datetime
import signal
import sys
from pathlib import Path

# Default configuration values
DEFAULT_PORT_FILE = "/var/run/auto-natpmp/port"
DEFAULT_GATEWAY_IP = "10.2.0.1"
DEFAULT_FORWARD_LIFETIME = 60  # seconds
DEFAULT_SLEEP_TIME = 45  # seconds
DEFAULT_LOG_FILE = "/var/log/auto-natpmp/auto-natpmp.log"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOCAL_PORT = 0
DEFAULT_EXTERNAL_PORT = 1

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='NAT-PMP port forwarding service with port tracking')
    
    parser.add_argument('--port-file', default=DEFAULT_PORT_FILE,
                        help=f'File to store the current public port (default: {DEFAULT_PORT_FILE})')
    parser.add_argument('--gateway-ip', default=DEFAULT_GATEWAY_IP,
                        help=f'Gateway IP address (default: {DEFAULT_GATEWAY_IP})')
    parser.add_argument('--lifetime', type=int, default=DEFAULT_FORWARD_LIFETIME,
                        help=f'Port forwarding lifetime in seconds (default: {DEFAULT_FORWARD_LIFETIME})')
    parser.add_argument('--sleep-time', type=int, default=DEFAULT_SLEEP_TIME,
                        help=f'Sleep time between iterations in seconds (default: {DEFAULT_SLEEP_TIME})')
    parser.add_argument('--log-file', default=DEFAULT_LOG_FILE,
                        help=f'Log file location (default: {DEFAULT_LOG_FILE})')
    parser.add_argument('--log-level', default=DEFAULT_LOG_LEVEL,
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help=f'Logging level (default: {DEFAULT_LOG_LEVEL})')
    parser.add_argument('--local-port', type=int, default=DEFAULT_LOCAL_PORT,
                        help=f'Local port to forward (default: {DEFAULT_LOCAL_PORT})')
    parser.add_argument('--external-port', type=int, default=DEFAULT_EXTERNAL_PORT,
                        help=f'External port to request (default: {DEFAULT_EXTERNAL_PORT})')
    
    return parser.parse_args()

def setup_logging(log_file, log_level):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("auto-natpmp")

def setup_port_directory(port_file, logger):
    """Ensure the directory for the port file exists."""
    port_dir = os.path.dirname(port_file)
    try:
        Path(port_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Port directory ensured: {port_dir}")
    except Exception as e:
        logger.error(f"Failed to create port directory: {e}")
        sys.exit(1)

def save_port_to_file(port, port_file, logger):
    """Save the current public port to the port file."""
    try:
        with open(port_file, 'w') as f:
            f.write(str(port))
        logger.info(f"Port {port} saved to {port_file}")
    except Exception as e:
        logger.error(f"Failed to write port to file: {e}")

def run_natpmpc_command(protocol, external_port, local_port, lifetime, gateway_ip, logger):
    """Run natpmpc command for the specified protocol and return output."""
    cmd = ["natpmpc", "-a", str(external_port), str(local_port), protocol, 
        str(lifetime), "-g", gateway_ip]
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"natpmpc command failed for {protocol}: {e}")
        logger.error(f"Error output: {e.stderr}")
        return None

def extract_public_port(output, logger):
    """Extract the public port from natpmpc output."""
    if not output:
        return None
    
    port_match = re.search(r"Mapped public port (\d+)", output)
    if port_match:
        return port_match.group(1)
    
    logger.warning("Could not find public port in output")
    logger.debug(f"Full output: {output}")
    return None

def setup_signal_handlers(port_file, logger):
    """Set up signal handlers for graceful shutdown."""
    def handle_exit(signum, frame):
        """Handle exit signals gracefully."""
        logger.info("Received signal to exit. Cleaning up...")
        try:
            if os.path.exists(port_file):
                os.remove(port_file)
                logger.info(f"Removed port file: {port_file}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

def main(port_file=DEFAULT_PORT_FILE, 
        gateway_ip=DEFAULT_GATEWAY_IP,
        forward_lifetime=DEFAULT_FORWARD_LIFETIME,
        sleep_time=DEFAULT_SLEEP_TIME,
        log_file=DEFAULT_LOG_FILE,
        log_level=DEFAULT_LOG_LEVEL,
        local_port=DEFAULT_LOCAL_PORT,
        external_port=DEFAULT_EXTERNAL_PORT):
    """Main function to run the NAT-PMP port forwarding loop."""
    
    # Setup logging
    logger = setup_logging(log_file, log_level)
    
    logger.info("Starting auto-natpmp service")
    logger.info(f"Configuration: Gateway={gateway_ip}, Lifetime={forward_lifetime}s, "
                f"Sleep={sleep_time}s, PortFile={port_file}, "
                f"Local Port={local_port}, External Port={external_port}")
    
    # Register signal handlers
    setup_signal_handlers(port_file, logger)
    
    # Ensure port directory exists
    setup_port_directory(port_file, logger)
    
    current_port = None
    
    try:
        while True:
            logger.info(f"Running NAT-PMP forwarding at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Run UDP forwarding
            udp_output = run_natpmpc_command("udp", external_port, local_port, 
                forward_lifetime, gateway_ip, logger)
            if not udp_output:
                logger.error("UDP forwarding failed, will retry")
                time.sleep(5)
                continue
            
            udp_port = extract_public_port(udp_output, logger)
            
            # Run TCP forwarding
            tcp_output = run_natpmpc_command("tcp", external_port, local_port, 
                forward_lifetime, gateway_ip, logger)
            if not tcp_output:
                logger.error("TCP forwarding failed, will retry")
                time.sleep(5)
                continue
            
            tcp_port = extract_public_port(tcp_output, logger)
            
            # Validate ports match
            if udp_port and tcp_port:
                if udp_port != tcp_port:
                    logger.warning(f"UDP port ({udp_port}) does not match TCP port ({tcp_port})")
                
                # Save port if it changed
                if current_port != tcp_port:
                    current_port = tcp_port
                    save_port_to_file(current_port, port_file, logger)
                    logger.info(f"Port updated to {current_port}")
            else:
                logger.warning("Failed to extract ports from output")
            
            # Sleep before next iteration
            time.sleep(sleep_time)
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    finally:
        # Cleanup on exit
        if os.path.exists(port_file):
            os.remove(port_file)
            logger.info(f"Removed port file: {port_file}")
    
    return 0

if __name__ == "__main__":
    # Parse command line arguments only when run as a script
    args = parse_arguments()
    
    # Call main with parsed arguments
    sys.exit(main(
        port_file=args.port_file,
        gateway_ip=args.gateway_ip,
        forward_lifetime=args.lifetime,
        sleep_time=args.sleep_time,
        log_file=args.log_file,
        log_level=args.log_level,
        local_port=args.local_port,
        external_port=args.external_port
    ))