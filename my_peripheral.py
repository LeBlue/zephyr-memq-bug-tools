

from pydbusbluez import format as fmt


from pydbusbluez import org_bluetooth

device_information_service = {
    'name': 'device_information',
    'uuid': '0000180a-0000-1000-8000-00805f9b34fb',
    'chars': [
            org_bluetooth.model_number_string,
            org_bluetooth.serial_number_string,
            org_bluetooth.firmware_revision_string,
            org_bluetooth.hardware_revision_string,
            org_bluetooth.software_revision_string,
            org_bluetooth.manufacturer_name_string,
    ]
}

# custom characteristic format
class CustomFormat(fmt.FormatTuple):
    sub_cls = (fmt.FormatUint8, fmt.FormatBitfield)
    sub_cls_names = ('state', 'errors')

# custom service
custom_service = {
    'name': 'custom_service',
    'uuid': '12345678-0000-1234-1234-123456789012',
    # list of custom characteristics
    'chars': [
        {
            "name": "custom_char",
            "uuid": "12345678-0001-1234-1234-123456789012",
            "form": fmt.FormatUint8,
        },
        {
            "name": "custom_format_char",
            "uuid": "12345678-0002-1234-1234-123456789012",
            "form": CustomFormat,
        }
    ]
}


#GATT = [device_information_service, custom_service]

class FormatHGPPushSettings(fmt.FormatTuple):
    sub_cls = [fmt.FormatUint8]
    sub_cls_names = ['long_push_duration']


class FormatHGPRotationSettings(fmt.FormatTuple):
    sub_cls = [fmt.FormatUint8, fmt.FormatUint8, fmt.FormatUint8]
    sub_cls_names = ['steps_per_event', 'resolution', 'display_resolution']


class FormatHGPRotationAction(fmt.FormatTuple):
    sub_cls = [fmt.FormatUint8, fmt.FormatUint8]
    sub_cls_names = ['events', 'direction']


class FormatHGPDeviceState(fmt.FormatTuple):
    sub_cls = [fmt.FormatUint8Enum, fmt.FormatBitfield]
    sub_cls_names = ['state', 'error']


class FormatHGPSystemSettings(fmt.FormatTuple):
    sub_cls = [fmt.FormatUint16, fmt.FormatUint16]
    sub_cls_names = ['standby_to', 'sleep_to']


class FormatHGPSystemState(fmt.FormatTuple):
    sub_cls = [fmt.FormatBitfield, fmt.FormatBitfield]
    sub_cls_names = ['state', 'error']


hgp_info_state = {
    'name': 'hgp_info_state',
    'uuid': '1ABE0010-F938-452D-AD9E-76EE1B548E51',
    'chars': [
            {'name': 'device_type',
                'uuid': '1ABE0011-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
            {'name': 'system_settings',
                'uuid': '1ABE0012-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPSystemSettings},
            {'name': 'device_temperature',
                'uuid': '00002a1f-0000-1000-8000-00805f9b34fb', 'form': org_bluetooth.FormatTemperatureCelsius},
            {'name': 'device_state',
                'uuid': '1ABE0013-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPDeviceState},
            {'name': 'system_state',
                'uuid': '1ABE0014-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPSystemState},
            {'name': 'program_state',
                'uuid': '1ABE0015-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
    ]
}


hgp_battery = {
    'name': 'hgp_battery',
    'uuid': '1ABE0020-F938-452D-AD9E-76EE1B548E51',
    'chars': [
            {'name': 'battery_settings',
                'uuid': '1ABE0021-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
            {'name': 'battery_level_state',
                'uuid': '2a1b', 'form': org_bluetooth.FormatBatteryLevelState},
            {'name': 'battery_temperature',
                'uuid': '00002a1f-0000-1000-8000-00805f9b34fb', 'form': org_bluetooth.FormatTemperatureCelsius},
            {'name': 'battery_charging_time',
                'uuid': '1ABE0022-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint16},
            {'name': 'qi_power_state',
                'uuid': '00002a1a-0000-1000-8000-00805f9b34fb', 'form': org_bluetooth.FormatBatteryPowerState},
    ]
}

hgp_user_input = {
    'name': 'hgp_user_input',
    'uuid': '1ABE0030-F938-452D-AD9E-76EE1B548E51',
    'chars': [
            {'name': 'hgp_input_settings',
                'uuid': '1ABE0031-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
            {'name': 'hgp_push_action',
                'uuid': '1ABE0032-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
            {'name': 'hgp_push_settings',
                'uuid': '1ABE0033-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPPushSettings},
            {'name': 'hgp_rotation_settings',
                'uuid': '1ABE0035-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPRotationSettings},
            {'name': 'hgp_rotation_action',
                'uuid': '1ABE0034-F938-452D-AD9E-76EE1B548E51', 'form': FormatHGPRotationAction},
            {'name': 'rotation_value',
                'uuid': '1ABE0036-F938-452D-AD9E-76EE1B548E51', 'form': fmt.FormatUint8},
    ]
}

GATT = [device_information_service, hgp_info_state, hgp_battery,
        hgp_user_input ]

