

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
            "name": "custom_char", # will be converted to object attribute key: custom_serverice.custom_char
            "uuid": "12345678-0001-1234-1234-123456789012", # length 4 UUIDs allowed
            "fmt": fmt.FormatUint8, # optional, defaults to fmt.FormatRaw (=bytes object)
        },
        {
            "name": "custom_format_char",
            "uuid": "12345678-0002-1234-1234-123456789012",
            "fmt": CustomFormat,
        }
    ]
}

# list expected of services
GATT = [
    device_information_service,
    custom_service,
]

