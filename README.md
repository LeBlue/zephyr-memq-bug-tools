# Multi connection bluetooth tester tools

Tools to test multiple simultaneous connection on bluez

relates to [https://github.com/zephyrproject-rtos/zephyr/issues/21107#issuecomment-586379867]


## Requirements

- Linux
- bluez
- python3
- [pydbus](https://github.com/LEW21/pydbus)
- [pydbus-bluez](https://github.com/LeBlue/pydbus-bluez)

## Installation

It is recommended to use a python virtual environment


### pydbus

Install the python3 pydbus package via pip3

Install the dependencies of pydbus, see [pydbus](https://github.com/LEW21/pydbus)
These should be available via the Linux distributions package manager (tested with fedora > 26, ubuntu 18.04)

This also means a python virtual environment needs access to system packages, for `venv` create it with
```
python3 -mvenv --system-site-packages venv_folder
source venv_folder/bin/activate

python3 -mpip install pydbus
```

To check the installation:
```
python3 -c 'from pydbus import SystemBus'
```

### pydbus-bluez

Install via git + pip

```
git clone https://github.com/LeBlue/pydbus-bluez.git
cd pydbus-bluez
python3 -mpip install .
```

### This repo

No need to install, just clone

```
git clone https://github.com/LeBlue/zephyr-memq-bug-tools.git
cd zephyr-memq-bug-tools
```


## Usage

See also `-h` option

```
./bt_conn_loop.py [-a hciX] [-g my_peripheral:GATT] mac1 [mac2 mac3 ...]
```

- This will (re)connect all peripherals by address (mac1, mac2, ...)
- after connection read ALL available values from device information service
- enable all notifications/indications (bluez hides the difference and calls both notify)
- print every characteristic value, that got changed (by read request or notify)
- regularly enable/disable scanning
- regularly read a specific value of ALL connected peripherals (**device information: software revision string**)


Now wait for 0.5-24 h for bug to appear.


### Configuration

GATT DB, optional

The program will load the GATT DB for `my_peripheral:GATT` variable (via -g parameter).
This is the GATT database description for the peripherals. This file might need customisation


### hci_usb sample/peripherals

To get a stable address, set it explicitly. e.g.


```
if  defined(CONFIG_SOC_FAMILY_NRF)
#include <nrfx.h>
#endif /* CONFIG_SOC_FAMILY_NRF */

/* in main */
#if defined(CONFIG_SOC_FAMILY_NRF)
   bt_addr_t sAddr;

   sys_put_le32(NRF_FICR->DEVICEADDR[0], &sAddr.val[0]);
   sys_put_le16(NRF_FICR->DEVICEADDR[1], &sAddr.val[4]);

   bt_ctlr_set_public_addr(sAddr.val);
#endif /* CONFIG_SOC_FAMILY_NRF */
```

Build config options:

```
CONFIG_BT_MAX_CONN=15

# allow changing value below
CONFIG_BT_CTLR_ADVANCED_FEATURES=y
# this must be increased from default=1
CONFIG_BT_CTLR_LLCP_CONN=15


CONFIG_USB=y
CONFIG_USB_DEVICE_STACK=y
CONFIG_USB_DEVICE_BLUETOOTH=y
CONFIG_USB_DEVICE_BLUETOOTH_VS_H4=y

CONFIG_LOG=y
CONFIG_UART_CONSOLE=y


```

### peripherals

Recommend to use the peripheral_sc_only, maybe with fixed passkey (and add device information service)

Configuration of my peripherals (parameter update req):
- conn_min/max:  22.50 msec (0x0012)
- latency: 4 (0x0004)
- supervision timeout: 7500 msec (0x02ee)



### Passkeys

For peripherals requireing a passkey, I use bt-agent from the bluez-tools package, install via package manager (or source: https://github.com/khvzak/bluez-tools)


For fixed passkeys, add a file e.g.`pins.cfg`:

```
DD:EE:FF:00:11:22 123456
```

Add agent to automatically reply to passkey requests. `bt-agent` needs a restart or -USR1 signal to reload `pins.cfg`

```
bt-agent -p pins.cfg -c KeyboardOnly
```





