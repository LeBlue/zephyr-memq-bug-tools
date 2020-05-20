#!/usr/bin/env python3

import sys
# some arguments
from argparse import ArgumentParser

# logging
import logging


# bluez-python bindings
import pydbusbluez as bluez
from pydbusbluez.format import FormatTuple, FormatRaw, FormatBase, FormatPacked, FormatUint

# Glib for dbus events
from gi.repository.GLib import MainLoop, timeout_add_seconds

# for gatt description import
from importlib import import_module


# callback for notify/indicate events
def generic_characteristic_notify(characteristic, value, peripheral, state_manager):
    '''
        changed event callback for a charcteristic
        note:
            it is not possible to distiguish between value changed because of
            notification/indication or a read from this or another process/thread
            and the bluez cached value got updated.

        notify/changed callbacks are setup depending on if the characteristic can notify/indicate or not

        characteristic:  bluez.GattCharacteristic
        value:           decoded value, type depends on characteristic
        peripheral:      bluez.Gatt
        state_manager:   StateManager
    '''

    state_manager.logger.info('Notification: %s %s.%s: %s', peripheral.name,
                characteristic.service.name,
                characteristic.name, str(value))


# callback for change characteristic values/read responses
def generic_characteristic_changed(characteristic, value, peripheral, state_manager):
    '''
        changed event callback for a charcteristic

        characteristic:  bluez.GattCharacteristic
        value:           decoded value, type depends on characteristic
        peripheral:      bluez.Gatt
        state_manager:   StateManager

    '''
    state_manager.logger.info('Changed value: %s %s.%s: %s', peripheral.name,
                            characteristic.service.name,
                            characteristic.name, str(value))

# (remote) device changed callbacks
def peripheral_changed(peripheral, changed_values, state_manager):
    '''
        changed event callback for peripherals

        peripheral:      bluez.Device
        changed_values:  dict
        state_manager:   StateManager

    '''

    # ignore these (peripheral.name == BD addr)
    d_addr = peripheral.name
    if not d_addr in state_manager.peripherals:
        return

    state_manager.logger.info('Device status changed: %s: %s', d_addr, str(changed_values))

    if 'Connected' in changed_values:
        if not changed_values['Connected']:
            state_manager.logger.error('Disconnected: %s %s', d_addr, str(peripheral))
            try:
                state_manager.adapter.scan(filters=state_manager.scan_filters)
            except Exception as e:
                state_manager.logger.error('Enableling scan failed: %s', str(e))
        else:
            state_manager.logger.info('Connected: %s %s', d_addr, str(peripheral))


    if 'ServicesResolved' in changed_values:
        if changed_values['ServicesResolved']:
            try:
                # load gatt database uuid matching
                state_manager.logger.info(
                    'Building GATT object: %s', d_addr)
                state_manager.peripherals[d_addr] = bluez.Gatt(peripheral, state_manager.gatt_description, warn_unmatched=False)
                state_manager.logger.info(
                    'Done GATT object: %s', d_addr)
            except Exception as e:
                state_manager.logger.error('ServiceResolved: %s: %s', d_addr, str(e))
                state_manager.peripherals[d_addr] = None

            # setup all callbacks
            if state_manager.peripherals[d_addr]:
                try:
                    enable_notifications(
                        state_manager.peripherals[d_addr], state_manager)
                    timeout_add_seconds(0, read_all, state_manager.peripherals[d_addr], state_manager)
                except bluez.BluezError as e:
                    state_manager.logger.error('ServiceResolved: %s: %s', d_addr, str(e))

        else:
            # clear gatt database mapping and callbacks
            if state_manager.peripherals[d_addr]:
                state_manager.peripherals[d_addr].clear()
                state_manager.peripherals[d_addr] = None

    if 'RSSI' in changed_values and not peripheral.connected:
        #pass
        device_discovered(peripheral, changed_values, state_manager)


def char_read_failed(char, err, state_manager):
    '''
        read characteristic async failed callback

        char:          bluez.GattCharacteristic
        err:           Exception instance
        state_manager: StateManager
    '''
    try:
        raise err
    except bluez.BluezError as e:
        state_manager.logger.error('Reading failed: %s %s', char.name, str(e))
    # Program error
    except Exception as e:
        state_manager.logger.error('Reading cb failed: %s %s', char.name, str(e))



def char_read_ok(characteristic, value, state_manager):
    '''
        read characteristic async done callback

        characteristic: bluez.GattCharacteristic
        value:          decoded value, type depends on characteristic
        state_manager:  StateManager
    '''
    if characteristic.obj:
        addr = ':'.join(characteristic.obj.split('/')[4].split('_')[1:])
    else:
        addr = '??'
    state_manager.logger.info('Read value: %s %s.%s: %s', addr,
                            characteristic.service.name,
                            characteristic.name, str(value))


def device_connect_failed(dev, err, state_manager):
    '''
        connect async failed callback

        dev:           bluez.Device
        state_manager: StateManager
    '''
    state_manager.logger.error('Connection failed: %s %s', dev.address, str(err))


def device_discovered(dev, properties, state_manager):
    '''
        device discovered callback

        dev:           bluez.Device
        properties:    dict with device properties
        state_manager: StateManager
    '''

    d_addr = dev.name.upper()
    state_manager.logger.info('Device discovered: %s %s', d_addr, dev.device_name)

    # ignore these
    if not d_addr in state_manager.peripherals:
        return

    dev.onPropertiesChanged(None)
    dev.onPropertiesChanged(peripheral_changed, state_manager)

    if dev.connected:
        # device was never disconnected, trigger bluez.Gatt object creation by faking event.
        state_manager.logger.info('Already connected: %s', d_addr)
        if dev.services_resolved:
            peripheral_changed(dev,
                               {'Connected': dev.connected, 'ServicesResolved': dev.services_resolved},
                               state_manager)
    else:
        state_manager.logger.info('Connecting: %s', d_addr)

        state_manager.adapter.scan(enable=False)

        # this requests connection asynchronous
        dev.connect_async(None, device_connect_failed, state_manager)


def device_removed(dev_path, state_manager):
    '''
        Callback for cleanup if bluez objects get removed

        dev_path:       dbus oject path
    '''
    for p_addr, db in state_manager.peripherals.items():
        # db = state_manager.peripherals[p_addr]
        if db and db.dev and db.dev.obj and db.dev.obj == dev_path:
            db.dev.clear()
            db.dev = None
            state_manager.peripherals[p_addr] = None

def adapter_changed(adapter, changed_values, state_manager):
    '''
        adapter changed callback

        adapter:         bluez.Adapter
        changed_values:  dict
        state_manager:   StateManager
    '''

    state_manager.logger.info('Adapter %s changed: %s', str(adapter.name), str(changed_values))
    if 'Powered' in changed_values:
        # adapter unpowerered/crashed etc
        if changed_values['Powered']:
            state_manager.logger.info('Adapter %s powered', str(adapter.name))
        else:
            state_manager.logger.error('Adapter %s unpowered', str(adapter.name))

            # remove all references of cached gatt objects
            for p_addr, db in state_manager.peripherals.items():
                if db:
                    db.clear()
                state_manager.peripherals[p_addr] = None

            # terminate glib mainloop and program
            state_manager.mainloop.quit()

    if 'Discovering' in changed_values:
        state_manager.logger.info('Adapter %s scanning: %s', str(adapter.name), changed_values['Discovering'])


def start_scanning(state_manager):
    state_manager.adapter.scan(filters=state_manager.scan_filters)
    return False

def toggle_scanning(state_manager):
    enable = not state_manager.adapter.scanning
    state_manager.adapter.scan(enable=enable, filters=state_manager.scan_filters)



def setup_logger():
    '''
        Basic log formating, returns logger instance
    '''
    logging.basicConfig(
        format='%(asctime)s;%(levelname)s;%(name)s;%(message)s', level=logging.INFO)

    # add logging for pydbusbluez
    bluez.Device.logger.setLevel(logging.INFO)
    bluez.Gatt.logger.setLevel(logging.INFO)

    # create 'main' logger
    logger = logging.getLogger('main')
    # this script logging level
    logger.setLevel(logging.INFO)

    return logger

def enable_notifications(gatt, state_manager):
    '''
        enable all notifications/indications if possible
        setup changed callbacks for all characteristics

        gatt:           bluez.Gatt
        state_manager:  StateManager
    '''
    for s in gatt.services:
        for c in s.chars:
            try:
                flags = c.flags
                state_manager.logger.debug('%s %s %s', str(c), c.name, flags)
                if 'notify' in flags or 'indicate' in flags:
                    if not c.notifying:
                        state_manager.logger.debug('not notifiying, enableing')
                    c.onValueChanged(
                        generic_characteristic_notify, gatt.dev, state_manager)
                    c.notifyOn()
                    if not c.notifying:
                        state_manager.logger.warning(
                            'not notifiying: %s', str(c))
                elif 'read' in flags:
                    c.onValueChanged(generic_characteristic_changed, gatt.dev, state_manager)
            except bluez.BluezDoesNotExistError as e:
                state_manager.logger.warning('%s: %s', str(gatt.dev), str(e))


def read_all(gatt, state_manager):
    # we'll hit dbus open reply limit if reading everything
    try:
        info = gatt.device_information
    except:
        return


    if info and info.chars:
        for c in info.chars:
            try:
                flags = c.flags
                state_manager.logger.debug('%s %s %s', str(c), c.name, flags)
                if 'read' in flags:
                    c.read_async(char_read_ok, char_read_failed, state_manager)
            except (bluez.BluezDoesNotExistError, bluez.DBusError) as e:
                state_manager.logger.warning('%s', str(e))

def read_timer_function(state_manager):
    '''
        Timer callback for repeatedly reading a specifig value
        Additionally still enable/disable scanning for BUG hunting
    '''

    state_manager.logger.info("Read timer expired")

    try:
        devs = state_manager.peripherals
        if state_manager.adapter.scanning:
            state_manager.adapter.scan(enable=False)

        missing_list = []

        # try sending a read request for all known and connected devices
        state_manager.logger.info('Reading software revision string')
        for addr in state_manager.peripheral_addresses:
            try:
                if devs[addr] and devs[addr].dev.connected:
                    # TODO read request device information
                    # response should be in peripheral_changed callback
                    #
                    # object is called like my_service_name.my_char_name, see GATT dictionary (names lowercased + snakecase)
                    devs[addr].device_information.software_revision_string.read_async(char_read_ok, char_read_failed, state_manager)
                    devs[addr].custom_service.custom_char.read_async(char_read_ok, char_read_failed, state_manager)

                    # TODO maybe add more read_async calls here
                else:
                    state_manager.logger.warning('Not connected %s', addr)
                    missing_list.append(addr)
            except Exception as e:
                state_manager.logger.warning('read timer %s: %s', addr, str(e))
                missing_list.append(addr)

        # TODO Force(!?) BUG by still scanning
        state_manager.adapter.scan(filters=state_manager.scan_filters)
        if missing_list:
            state_manager.logger.warning('Expected devices not connected: %s', len(missing_list))

    # make sure, timer gets repeated on crash: catch all programming errors
    except Exception as e:
        state_manager.logger.error("Read timer failed: %s", str(e))

    # return True to repeat timer on initial timeout
    return True



def cli_arguments():
    parser = ArgumentParser(
        description='Peripheral connect and print all changed signals')

    _def_adapter = 'hci0'
    _def_scan = 5

    parser.add_argument('-i', '--adapter', metavar='hciX', default=_def_adapter,
                        help='bluetooh adapter to use (default={})'.format(_def_adapter))

    parser.add_argument('-g', '--gatt', metavar='MOD', default=None, help='gatt description to import (PACKAGE.MODULE:[GATT_VARIABLE]')

    parser.add_argument('peripheral_addresses',nargs='*', default=None, help='device address(es) to connect to')

    args = parser.parse_args()

    print(args)
    if len(args.peripheral_addresses) == 0:
        print('No device/peripheral addresses given, try --help')
        sys.exit(1)

    return args




# holds instance, that we can pass around to callbacks etc.
class StateManager(object):
    def __init__(self, adapter_name, peripheral_addresses, logger, gatt_description):
        self.adapter_name = adapter_name
        self.peripheral_addresses = peripheral_addresses
        self.logger = logger
        self.scan_filters = {'Transport': 'le'}

        self.mainloop = MainLoop.new(None, False)
        # Use same gatt description for all peripherals (matching uuids to names/formats)
        self.gatt_description = gatt_description

        # state information for all peripherals we want to interact with, dictionary with addr as key
        self.peripherals = {}
        for idx, p_addr in enumerate(self.peripheral_addresses):
            # use upper case addresses
            self.peripheral_addresses[idx] = p_addr.upper()
            self.peripherals[p_addr.upper()] = None

        try:
            self.init_adapter()
        except bluez.BluezError as e:
            logger.error(str(e))
            bluez.ObjectManager.get().onAdapterAdded(adapter_added, self.adapter_name, self)


    def init_adapter(self):
        self.adapter = bluez.Adapter(self.adapter_name)
        self.adapter.onPropertiesChanged(
            adapter_changed, state_manager=self)
        self.adapter.onDeviceAdded(device_discovered, self, init=True)

        # queue function for execution in GLib mainloop
        self.adapter.onDeviceRemoved(device_removed, self)

        # queue function for execution in GLib mainloop
        timeout_add_seconds(0, start_scanning, self)

        # read a value every 10 seconds
        timeout_add_seconds(10, read_timer_function, self)



    def run(self):
        self.mainloop.run()

def adapter_added(om, adapter_path, ifaces, adapter_name, state_manager):
    try:
        adapter = bluez.Adapter(adapter_path.split('/')[-1])
        if adapter.name == state_manager.adapter_name:
            state_manager.init_adapter()
    except bluez.BluezError as e:
        state_manager.logger.error("Adapter added failed: %s", str(e))

def main():

    args = cli_arguments()
    logger = setup_logger()

    # load user provided gatt description dictionary
    # see my_peripheral.py as example
    if args.gatt:
        gatt_module = args.gatt.split(':')[0]
        try:
            gatt_mod = import_module(gatt_module)
        except ImportError as e:
            print('Failed to import gatt profile module:', str(e), file=sys.stderr)
            sys.exit(1)
        try:
            gatt_var = 'GATT'
            if len(args.gatt.split(':')) > 1:
                gatt_var = args.gatt.split(':')[1]
            GATT = getattr(gatt_mod, gatt_var)
        except AttributeError as e:
            print('Failed to import gatt profile:', str(e), file=sys.stderr)
            GATT = []
    else:
        # will use bluez default numbered names for everything an bytes/raw value formating
        GATT = []

    print('Expecting GATT db:', GATT)

    state_manager = StateManager(args.adapter, args.peripheral_addresses, logger, GATT)


    try:
        state_manager.run()
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        print('Exit')



if __name__ == "__main__":
    main()


