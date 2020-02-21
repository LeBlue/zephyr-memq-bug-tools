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
from gi.repository.GObject import MainLoop
from gi.repository.GLib import timeout_add_seconds

# GATT database of peripherals, seperate file
from my_peripheral import GATT


# callback for notify/indicate events
def generic_characteristic_notify(characteristic, value, peripheral, state_manager):
    '''
        changed event callback for a charcteristic
        note:
            it is not possible to distiguish between value changed because of
            notification/indication or from another process/thread triggered a read
            and the bluez cashed value got updated.

        notify/changed callbacks are setup depending on if the characteristic can notify/indicate or not

        characteristic:  bluez.GattCharacteristic
        value:           decoded type depends on characteristic
        peripheral:      bluez.Gatt
        state_manager:   StateManager
    '''

    state_manager.logger.info('Notification: %s %s.%s: %s', peripheral.name,
                characteristic.service.name,
                characteristic.name, str(value))


# callback for notify/indicate events
def generic_characteristic_changed(characteristic, value, peripheral, state_manager):
    '''
        changed event callback for a charcteristic

        characteristic:  bluez.GattCharacteristic
        value:           decoded type depends on characteristic
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

        peripheral:      bluez.Gatt
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

            state_manager.adapter.scan()
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
                    timeout_add_seconds(1, read_all, state_manager.peripherals[d_addr], state_manager)
                except bluez.BluezError as e:
                    state_manager.logger.error('ServiceResolved: %s: %s', d_addr, str(e))

        else:
            state_manager.peripherals[d_addr].clear()
            state_manager.peripherals[d_addr] = None

    if 'RSSI' in changed_values and not peripheral.connected():
        #pass
        device_discovered(peripheral, state_manager)



def device_discovered(dev, state_manager):
    '''
        device discovered callback

        dev:           bluez.Device
        state_manager: StateManager
    '''

    d_addr = dev.name.upper()
    state_manager.logger.info('Device discovered: %s', d_addr)

    # ignore these
    if not d_addr in state_manager.peripherals:
        return

    dev.onPropertiesChanged(peripheral_changed, state_manager)



    if dev.connected():
        # device was never disconnected, trigger bluez.Gatt object creation by faking event.
        state_manager.logger.info('Already connected: %s', d_addr)
        peripheral_changed(dev,
                           {'Connected': dev.connected(), 'ServicesResolved': dev.services_resolved},
                           state_manager)
    else:
        state_manager.logger.info('Connecting: %s', d_addr)

        state_manager.adapter.scan(enable=False)

        # this requests connection asynchronous
        dev.connect_async()

        # this connects syncronous
        # try:
        #     dev.connect()
        # except bluez.BluezError as e:
        #     state_manager.logger.error('Connecting: %s failed: %s', dev.name, str(e))
        #     state_manager.adapter.scan()


def device_removed(dev_path, state_manager):
    '''
        Callback for cleanup if bluez objects get removed

        dev_path:       dbus oject path
    '''
    for p_addr, _ in state_manager.peripherals:
        db = state_manager.peripherals[p_addr]
        if db and db.dev and db.dev.obj and db.dev.obj == dev_path:
            db.dev.clear()
            db.dev = None
            state_manager.peripherals[p_addr] = None

def adapter_changed(adapter, new_value, state_manager):
    '''
        adapter changed callback

        adapter      :   bluez.Adapter
        new_value    :   dict
        state_manager:   StateManager
    '''

    state_manager.logger.info('Adapter %s changed: %s', str(adapter.name), str(new_value))
    if 'powered' in new_value:
        # adapter unpowerered/crashed etc
        if not new_value['powered']:
            state_manager.logger.error('Adapter %s unpowered', str(adapter.name))

            # remove all references of cached gatt objects
            for p_addr, _ in state_manager.peripherals:
                state_manager.peripherals[p_addr].clear()
                state_manager.peripherals[p_addr] = None

            # terminate glib mainloop
            state_manager.loop.quit()

    if 'Discovering' in new_value:
        state_manager.logger.info('Adapter %s scanning: %s', str(adapter.name), new_value['Discovering'])


def start_scanning(state_manager):
    state_manager.adapter.scan()
    return False

def toggle_scanning(state_manager):
    state_manager.adapter.scan()


def init_devices(state_manager):
    for d in state_manager.adapter.devices():
        device_discovered(d, state_manager)

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
                flags = c.flags()
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
    for s in gatt.services:
        for c in s.chars:
            try:
                flags = c.flags()
                state_manager.logger.debug('%s %s %s', str(c), c.name, flags)
                if 'read' in flags:
                    c.read_async()
            except bluez.BluezDoesNotExistError as e:
                state_manager.logger.warning('%s', str(e))

def read_timer_function(state_manager):
    '''
        Timer callback for repeatedly reading a specifig value
        Additionally still enable/disable scanning for BUG hunting
    '''
    try:
        devs = state_manager.peripherals
        if state_manager.adapter.scanning():
            state_manager.adapter.scan(enable=False)

        peripheral_missing = False

        # try sending a read request for all known and connected devices
        state_manager.logger.info('Reading software revision string')
        for addr in state_manager.cli_args.peripheral_addr:
            try:
                if devs[addr] and devs[addr].dev.connected():
                    # TODO read request device information
                    # response should be in peripheral_changed callback
                    #
                    # object is called like my_service_name.my_char_name, see GATT dictionary
                    devs[addr].device_information.software_revision_string.read_async()
                else:
                    state_manager.logger.warn('Not connected %s', addr)
                    peripheral_missing = True
            except Exception as e:
                state_manager.logger.warn('read timer %s: %s', addr, str(e))
                peripheral_missing = True

        # TODO choose one
        # unconnected peripheral, rescan
        # if peripheral_missing:
        #     state_manager.adapter.scan()

        #
        # TODO Force(!?) BUG by still scanning
        state_manager.adapter.scan()


    # make sure, timer gets repeated on crash: catch all programming errors
    except Exception:
        pass

    # return True to repeat timer on initial timeout
    return True



def cli_aruments():
    parser = ArgumentParser(
    description='Peripheral connect and print all changed signals (for "my_peripheral.GATT")')

    _def_adapter = 'hci0'
    _def_scan = 5

    parser.add_argument('-i', '--adapter', metavar='hciX', default=_def_adapter,
                        help='bluetooh adapter to use (default={})'.format(_def_adapter))

    # UNUSED/TODO
    parser.add_argument('-d', '--scan-duration', metavar='sec', default=_def_scan, type=int,
                        help='scan duration in seconds (default={}), UNUSED'.format(_def_scan))

    parser.add_argument('peripheral_addr',nargs='*', default=None, help='device address(es) to connect to')

    # UNUSED/TODO
    parser.add_argument('-n', '--no-pair', default=False, action='store_true',
                         help='do not try to pair device, if not already done (default=False, meaning DO pair), UNUSED')

    args = parser.parse_args()

    print(args)
    if len(args.peripheral_addr) == 0:
        print('No device/peripheral addresses given, try --help')
        sys.exit(1)

    return args




# holds instance, that we can pass around to callbacks etc.
class StateManager(object):
    def __init__(self, cli_args, logger, gatt_description):
        self.cli_args = cli_args
        self.logger = logger


        self.mainloop = MainLoop.new(None, False)
        # Use same gatt description for all peripherals (matching uuids to names/formats)
        self.gatt_description = gatt_description

        # state information for all peripherals we want to interact with, dictionary with addr as key
        self.peripherals = {}
        for idx, p_addr in enumerate(self.cli_args.peripheral_addr):
            # use upper case addresses
            self.cli_args.peripheral_addr[idx] = p_addr.upper()
            self.peripherals[p_addr.upper()] = None

        try:
            self.init_adapter()
        except bluez.BluezError as e:
            logger.error(str(e), file=sys.stderr)
            sys.exit(1)


    def init_adapter(self):
        self.adapter = bluez.Adapter(self.cli_args.adapter)
        self.adapter.onPropertiesChanged(
            adapter_changed, state_manager=self)
        self.adapter.onDeviceAdded(device_discovered, self)
        self.adapter.onDeviceRemoved(device_removed, self)

        # queue function for execution in GLib mainloop
        timeout_add_seconds(0, start_scanning, self)
        timeout_add_seconds(0, init_devices, self)

        # read a value every 10 seconds
        timeout_add_seconds(10, read_timer_function, self)


    def run(self):
        self.mainloop.run()

def main():

    args = cli_aruments()
    logger = setup_logger()

    state_manager = StateManager(args, logger, GATT)


    try:
        state_manager.run()
    except (KeyboardInterrupt, SystemExit):
        print('Exit')



if __name__ == "__main__":
    main()


