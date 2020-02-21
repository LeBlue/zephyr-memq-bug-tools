#!/usr/bin/env python3

import sys
from argparse import ArgumentParser

import pydbusbluez as bluez
from pydbusbluez.format import FormatTuple, FormatRaw, FormatBase, FormatPacked, FormatUint

from gi.repository.GObject import MainLoop
from gi.repository.GLib import timeout_add_seconds


from my_peripheral import GATT

import cmd
import time
import ast


def generic_notify(gatt_char, new_value):
    print('Value changed:', _make_id(gatt_char.name), str(new_value))


def dev_connected_changed(dev, new_value):
    print('Device status changed:', str(new_value))
    if 'Connected' in new_value:
        if not new_value['Connected']:
            print('Disconnected:', str(dev))


def adapter_changed(adap, new_value):
    print('Adapter changed:', str(new_value))


class CmdTimeout(object):

    def __init__(self, timeout_secs, loop):
        self.timeout = timeout_secs
        self.remaining = timeout_secs
        self.canceled = False
        def mainloop_quit():
            loop.quit()

        self.expired_cb = mainloop_quit
        timeout_add_seconds(1, self._tick)


    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0 and not self.canceled:
            self.canceled = True
            if self.expired_cb:
                self.expired_cb()
            return False

        return not self.canceled

def bt_connect(adapter, addr, timeout):
    d = None
    try:
        adapter_obj = bluez.Adapter(adapter)
        devs = adapter_obj.devices():
        for d in devs:
            if d.name == addr.upper():
                break
        if not d:
            adapter_obj.scan()
            time.sleep(timeout)

        devs = adapter_obj.devices():
        for d in devs:
            if d.name == addr.upper():
                break

        if d:
            d.connect()
        if d.connected():
            return Gatt(d, GATT)

    except bluez.BluezError as e:
        print('Failed:', str(e), file=sys.stderr)





def main():
    parser = ArgumentParser(description='BT (my_peripheral) command interpreter')
    parser = ArgumentParser(
    description='Peripheral connect and set/get values (for "my_peripheral.GATT")')

    _def_adapter = 'hci0'
    _def_scan = 5

    parser.add_argument('-i', '--adapter', metavar='hciX', default=_def_adapter,
                        help='bluetooh adapter to use (default={})'.format(_def_adapter))

    parser.add_argument('-d', '--scan-duration', metavar='sec', default=_def_scan, type=int,
                        help='scan duration in seconds (default={})'.format(_def_scan))

    parser.add_argument('-a', '--address', nargs='?', default=None, help='device address(es) to connect to')


    parser.add_argument('script', default=None, nargs='*', type=str, help='commands to run from script(s), see the run/record commands')

    parser.convert_arg_line_to_args = lambda self, arg_line: arg_line.split()

    print(parser)
    args = parser.parse_args()


    gatt = None
    if args.address:
        gatt = bt_connect(args.adapter, args.address, args.scan_duration)


    shell = BTShell(gatt, args)
    shell.make_prompt()
    # add connect command
    shell.cmdqueue.append('connect '+ args.device)
    try:
        for script in args.script:
            with open(script) as f:
                shell.cmdqueue.extend(f.read().splitlines())
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print('quit')


def _make_id(s):
    id = s.lower().replace(' ', '_').replace('-', '_')
    if id.isidentifier():
        return id

    #TODO
    raise ValueError('Invalid id: {}'.format(id))

def _gatt_valid(gatt):
    try:
        if gatt and gatt.dev and gatt.dev.connected():
            return True
    except bluez.BluezError:
        pass
    return False

class BTShell(cmd.Cmd):
    intro = 'Welcome to the BT test shell.   Type help or ? to list commands.\n'
    prompt = '(bt) '
    file = None

    def __init__(self, gatt, cli_args,  *args, **kwargs):
        self.gatt = gatt
        self.cli_args = cli_args
        self.clp_cache = self.build_clpt_cache(GATT)
        self.autoconnect = False
        self.autoconnecting = False
        super().__init__(*args, **kwargs)

    def make_prompt(self):
        if _gatt_valid(self.gatt):
            self.prompt = '{}{} $ '.format(BTshell.prompt, self.gatt.dev.name)
        else:
            if self.autoconnect:
                # try only once
                if self.autoconnecting:
                    self.autoconnecting = False
                    self.autoconnect = True
                else:
                    self.autoconnecting = True
                    self.cmdqueue.append('connect ' + self.cli_args.device)
            else:
                self.prompt = '{}{} $ '.format(BTshell.prompt, 'disconnected')

    def build_clpt_cache(self, gatt_desc):
        ca = []
        for s in gatt_desc:
            for c in s['chars']:
                el = _make_id(c['name'])
                ca.append(el)
        return ca

    def find_char_obj(self, name):
        if self.gatt:
            for s in self.gatt.services:
                for c in s.chars:
                    if _make_id(c.name) == name:
                        return c

        else:
            print('Disconnected')
            if self.autoconnect:
                self.cmdqueue.append('connect ' + self.cli_args.device)

        return None

    def _char_names_complete(self, text, line, begidx, endidx):
        if not text:
            return self.clp_cache
        clp = [arg for arg in self.clp_cache if arg.startswith(text)]
        return clp

    # ----- basic bt commands -----
    def do_set(self, arg):
        'set a value'
        args = _parse_args_simple(arg)
        if len(args) < 2:
            print('set: Need an argument, simple python types, e.g 1, "foo", (1, 5), [0,4,5]', file=sys.stderr)

        o = self.find_char_obj(args[0])
        if not o:
            print('set: Not valid:', args[0])
            return
        try:
            exp_arg = ' '.join(args[1:])
            #print('arg is: \'{}\''.format(exp_arg))
            v = ast.literal_eval(exp_arg)
        except (ValueError, SyntaxError) as e:
            print('set: ', arg, str(e), file=sys.stderr)
            return
        try:
            exp = o.form(v)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return
        try:
            o.write(exp)
        except bluez.BluezError as e:
            print('set: ', arg, str(e), file=sys.stderr)




    def complete_set(self, text, line, begidx, endidx):
        if len(line) != endidx:
            return None
        pl = _parse_args_simple(line)

        if len(pl) < 2 or (len(pl) == 2 and line[-1] != ' '):
            return self._char_names_complete(text, line, begidx, endidx)

        o = self.find_char_obj(pl[1])
        if not o:
            print('complete not foud: ', pl[1], file=sys.stderr)
            return None
        if not o.form:
            print('format not foud: ', pl[1], file=sys.stderr)
            return None

        return None

    def do_get(self, arg):
        'get (fetch) a characteristic value or all values'
        #print(arg)
        g_chars = _parse_args_simple(arg)
        #print(str(arg.split(' ')))
        if not g_chars:
            g_chars = self.clp_cache
        #print('reading: ', str(g_chars))

        for g_char in g_chars:
            o = self.find_char_obj(g_char)
            if not o:
                print(
                    'get:', g_char, 'Not valid in GATT database or not resolved', file=sys.stderr)
                continue
            try:
                v = o.read()
            except bluez.BluezError as e:
                print('get: ', g_char, str(e), file=sys.stderr)
                continue

            print(_make_id(o.name), v, file=sys.stderr)

    def complete_get(self, text, line, begidx, endidx):
        if len(line) != endidx:
            return None
        return self._char_names_complete(text, line, begidx, endidx)

    def do_info(self, arg):
        'show information about characteristic value type'
        g_chars = _parse_args_simple(arg)
        print(str(arg.split(' ')))
        if len(g_chars) != 1:
            print('info: Expectect one arugment', file=sys.stderr)
            return
        o = self.find_char_obj(g_chars[0])
        print('Service:', str(o.service))
        print('Char   :', str(o))
        if not issubclass(o.form, FormatBase):
            print('Unkown format', file=sys.stderr)
        else:
            print('Format :', str(o.form), file=sys.stderr)

    complete_info = _char_names_complete

    def do_value(self, arg):
        'Get the last known value of characteristic'
        print(arg)
        g_chars = _parse_args_simple(arg)
        if not g_chars:
            g_chars = self.clp_cache

        for g_char in g_chars:
            o = self.find_char_obj(g_char)
            if not o:
                print('value:', g_char, 'Not valid in GATT database', file=sys.stderr)
                continue
            try:
                v = o.value
            except bluez.BluezError as e:
                print('value:', o.name, str(e), file=sys.stderr)
                return

            print(o.name, v)

    complete_value = _char_names_complete

    def do_autoconnect(self, arg):
        'reconnect on disconnection before next command'
        self.autoconnect = True

    def do_connect(self, arg):
        'connect device or select device for interaction. When no paramter is given, -a option or last parameter will be used as address'
        args = _parse_args_simple(arg)
        if len(args) == 0:
            if _gatt_valid(self.gatt) and self.gatt.dev.connected():
                print('Already connected', file=sys.stderr)
                return

        elif len(args) > 1:
            print('At most one argument expected (device address)', file=sys.stderr)
            return
        else:
            self.cli_args.device = args[0]

        if _gatt_valid(self.gatt) and self.gatt.dev.name.lower() == args[0].lower() and self.gatt.dev.connected():
            print('Already connected', file=sys.stderr)
            return
        self.gatt = None

        try:
            self.gatt = bt_connect(self.cli_args.adapter, self.cli_args.device, self.cli_args.scan_duration)
            print('Connected', file=sys.stderr)
        except bluez.BluezError as e:
            print('connect', str(e), file=sys.stderr)

    def complete_connect(self, text, line, begidx, endidx):
        if len(line) != endidx:
            return None
        pl = _parse_args_simple(line)

        if len(pl) == 2 or (len(pl) == 2 and line[-1] != ' '):
            try:
                hci = bluez.Adapter(self.cli_args.adapter)
                devs = hci.devices()

            except bluez.BluezError:
                print('autocomplete failed', file=sys.stderr)
                return None
            return [ d.name for d in devs if d.name.lower().startswith(text.lower()) ]

        return None

    def do_disconnect(self, arg):
        'disconnect device currently selected device'
        if self.gatt and self.gatt.dev and self.gatt.dev.connected():
            g = self.gatt
            self.gatt = None
            g.dev.disconnect()

        else:
            self.gatt = None
        print('Disconnected', file=sys.stderr)

    def do_sleep(self, arg):
        'sleep for n seconds'
        args = _parse_args_simple(arg)
        if not args:
            print('Need number of seconds as argument', file=sys.stderr)
        try:
            s = int(args[0])
        except Exception as e:
            print(str(e))
            return

        time.sleep(s)

    def do_echo(self, arg):
        print(arg, file=sys.stderr)

    def default(self, line):
        args = _parse_args_simple(line)
        if not args[0].startswith('#'):
            print('Unkonwn commmand:', args[0], file=sys.stderr)
        else:
            if line[1:2]:
                print(line[1:])
            else:
                print(line[2:])

    def do_notify(self, arg):
        'enable all notifications and print changed values'
        args = _parse_args_simple(arg)
        timeout_seconds = None
        if len(args) > 0:
            try:
                timeout_seconds = int(args[0])
            except Exception as e:
                print(str(e))
                return

        for s in self.gatt.services:
            for c in s.chars:
                try:
                    flags = c.flags()
                    if 'notify' in flags or 'indicate' in flags:
                        c.onValueChanged(generic_notify)
                        c.notifyOn()
                    elif 'read' in flags:
                        c.onValueChanged(generic_notify)

                except bluez.BluezDoesNotExistError as e:
                    print(c.name, str(e), file=sys.stderr)

        loop = MainLoop.new(None, False)

        self.gatt.dev.onPropertiesChanged(dev_connected_changed)
        timeout = None
        if timeout_seconds:
            timeout = CmdTimeout(timeout_seconds, loop)
        try:
            if timeout_seconds:
                print('Notifying for {} seconds'.format(
                    timeout_seconds), file=sys.stderr)
            else:
                print('Notifiying, CTRL+C to end', file=sys.stderr)

            loop.run()
        except (KeyboardInterrupt, bluez.BluezError) as e:
            print('aborted:', self.gatt.dev.name, str(e), file=sys.stderr)
            loop.quit()
            if timeout:
                timeout.canceled = True




    def do_quit(self, arg):
        self.close()
        return True

    # ----- record and playback -----
    def do_record(self, arg):
        'Save future commands to filename: record somefile.btsh'
        self.file = open(arg, 'w')

    def do_run(self, arg):
        'Run commands from a file: somefile.btsh'
        self.close()
        try:
            with open(arg) as f:
                self.cmdqueue.extend(f.read().splitlines())
        except Exception as e:
            print('run:', arg, str(e))

    def precmd(self, line):
        if self.file and 'run' not in line:
            print(line, file=self.file)
        return line

    def postcmd(self, stop, line):
        if stop:
            return True

        self.make_prompt()
        return False

    def emptyline(self):
        pass

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


def _parse_args_simple(arg):
    return [ a for a in arg.split(' ') if a != '' ]


if __name__ == '__main__':
    main()
