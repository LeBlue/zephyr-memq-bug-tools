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
```
python3 -mpip install --user virtualenv
```

### pydbus

Install the python3 pydbus package via pip3

Install the dependencies of pydbus, see [pydbus](https://github.com/LEW21/pydbus)
These should be available via the Linux distributions package manager (tested with fedora > 26)

This also means a python virtual needs access to system packages, for `virtualenv` create it with
```
python3 -mvirtuelenv -p python3 --system-site-packages venv_folder
source venv_folder/bin/activate

python3 -mpip install pydbus
```

To check the installation :
```
python3 -c 'from pydbus import SystemBus'
```

### pydbus-bluez

Install via git + git

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
./bt_conn_loop.py [-a hciX] [mac1 mac2 mac3 ...]
```

- This will (re)connect all peripherals by address (mac1, mac2, ...)
- after connection read ALL available values
- enable all notifications/indications (bluez hides the difference and calls both notify)
- print every characteristic value, that got changed (by read request or notify)
- regularly enable/disable scanning
- regularly read a specific value of ALL connected peripherals

### Configuration

GATT DB

The programs will try to import the `my_peripheral.GATT` variable. This is the GATT database description for the peripherals. This file might need customisation


```
./bt_shell.py




### hci_usb sample

To get a stable address, set it explicitly. e.g.


```
if  defined(CONFIG_SOC_FAMILY_NRF)
#include <nrfx.h>
#endif /* CONFIG_SOC_FAMILY_NRF */
```

```
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

CONFIG_BLUETOOTH_INT_EP_MPS=64


### peripherals




### Passkeys

For peripherals requireing a passkey, use bt-agent from the bluez-tools package, install via package manager


For fixed passkeys, add a file e.g.`pins.cfg`:

```
DD:EE:FF:00:11:22 123456
```

Add agent to automatically reply to passkey requests. `bt-agent` needs a restart or -USR1 signal to reload `pins.cfg`

```
bt-agent -p pins.cfg -c KeyboardOnly
```





