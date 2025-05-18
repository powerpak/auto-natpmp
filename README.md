# auto-natpmp

This is a Python project that can run on any Linux, on hardware as small as a [Raspberry Pi][rpi].

It manages a request for a continuously forwarded port from an upstream gateway using the `natpmpc` utility from the [libnatpmp](https://github.com/miniupnp/libnatpmp.git) project. The number of the public port is saved to a file so that other programs can access it. It can be run interactively, but it is designed to run in the background as a [supervisord][] daemon.

## Getting started

1. Whether running on a [Raspberry Pi][rpi] or something else, you'll need a Linux with Python >=3.11 and the usual build tools. This is fulfilled by the default Raspberry Pi OS, which is based on Debian 12 (bookworm).

2. Install the latest version of libnatpmp with:

    ```
    $ cd /tmp
    $ git clone https://github.com/miniupnp/libnatpmp.git
    $ cd libnatpmp
    $ make all
    $ sudo make install
    ```

    This is preferable to using the Debian packaged version, which is quite out of date. If the installation worked, you should have `natpmpc` somewhere on your PATH.

3. Clone this repo, and then run `./auto-natpmp.py` to kick off the NAT-PMP request and monitoring cycle. Messages will be printed to `STDERR` and if successful the public port number on the gateway will be saved in `/tmp/auto-natpmp-port`.

[rpi]: https://www.raspberrypi.com/products/
[supervisord]: http://supervisord.org/introduction.html

## Running auto-natpmp as a daemon

I recommend using [supervisord]() to do this, 
which avoids the trouble of writing and installing `rc.d` scripts or mucking with `systemd`. A quick intro of how this would work on an RPi is in
[this StackExchange answer](https://raspberrypi.stackexchange.com/a/96676).

A sample supervisord configuration file that can be dropped into `/etc/supervisor/conf.d` is included in this repo. The script assumes that you've created a low-privilege user named `auto-natpmp`, that this code is checked out at `/opt/auto-natpmp`, the port file should be at `/var/run/auto-natpmp/port`, and logging to `/var/log/auto-natpmp/auto-natpmp.log`. To set up that user and the log directory correctly (Debian distros):

```
$ sudo adduser --system --no-create-home --disabled-login auto-natpmp
$ sudo mkdir -p /var/log/auto-natpmp
$ sudo chown -R natpmp-user:nogroup /var/log/auto-natpmp
$ sudo chmod 755 /var/log/auto-natpmp
```

## Author

[Theodore Pak](https://github.com/powerpak)

## License

MIT. See LICENSE.txt