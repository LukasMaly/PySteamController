from time import sleep

import pywinusb.hid as hid


class Control:
    """Class for handling the controls.

    Attributes:
        event (function): Function called when the control is used.
            The passed parameters are current value and previous value.
    """

    def __init__(self, name):
        """Initialize the Control class.

        Args:
            name (str): Name of the control.
        """

        self._name = name
        self.current_value = None
        self.previous_value = None
        self.event = None

    def update_value(self, current_value):
        """Update the control's value.

        Calls an event if the control is used.

        Args:
            current_value: Current control's value.
        """

        self.previous_value = self.current_value
        self.current_value = current_value

        try:  # current_value is iterable
            is_true = any(self.current_value) or any(self.previous_value)
        except TypeError:  # current_value is not iterable
            is_true = bool(self.current_value) or bool(self.previous_value)

        # call an event if current or previous value is non-zero
        if is_true and self.event is not None:
            self.event(self.current_value, self.previous_value)


class SteamController:
    """Class for handling the communication with the Steam Controller."""

    target_vendor_id = 0x28de  # Valve Software
    target_product_id = 0x1142  # Steam Controller

    # names of Steam Controller buttons
    buttons_names = [
        'RightTrigger', 'LeftTrigger', 'RightBumper', 'LeftBumper', 'Y', 'B',
        'X', 'A', 'LeftPad', 'Back', 'Guide', 'Start', 'LeftGrip', 'RightGrip',
        'LeftPad_Click', 'RightPad_Click', 'LeftPad_Touch', 'RightPad_Touch',
        'UNKNOWN0', 'LeftStick_Click', 'UNKNOWN1'
    ]

    # names of Steam Controller axes
    axes_names = [
        'LeftTrigger', 'RightTrigger', 'LeftStick', 'LeftPad', 'RightPad'
    ]

    def __init__(self):
        """Initialize the SteamController class."""

        self.buttons = {button_name: Control(button_name) for button_name in SteamController.buttons_names}
        self.axes = {axis_name: Control(axis_name) for axis_name in SteamController.axes_names}
        self._update_buttons_values([False] * 8 + [tuple([False] * 4)] + [False] * 8)
        self._update_axes_values([0, 0, (0, 0), (0, 0), (0, 0)])
        self._is_open = False

    def open(self):
        """Open the Steam Contoller and start receiving the data."""

        # get the Steam Controller device
        my_hid_target = hid.HidDeviceFilter(
            vendor_id=SteamController.target_vendor_id,
            product_id=SteamController.target_product_id)
        all_devices = my_hid_target.get_devices()
        for device in all_devices:
            if 'MI_01' in device.instance_id:  # get device with interface number 1
                break
        else:
            raise IOError  # the device was not found

        try:
            device.open()
            self._is_open = True
            # set custom raw data handler
            device.set_raw_data_handler(self.sample_handler)
            while self._is_open and device.is_plugged():
                # just keep the device opened to receive events
                sleep(0.5)
        finally:
            device.close()

    def close(self):
        """Close the Steam Controller."""

        self._is_open = False

    def sample_handler(self, data):
        """Handle the received data.

        Args:
            data (list of int): The list of received bytes.
        """

        if data[3] == 0:  # disconnected
            pass
        if data[3] == 1:  # is active
            # buttons
            current_buttons_vals = SteamController.to_bool_array(data[9]) + SteamController.to_bool_array(data[10]) + SteamController.to_bool_array(data[11])
            current_buttons_vals = current_buttons_vals[:8] + [tuple(current_buttons_vals[8:12])] + current_buttons_vals[12:]
            self._update_buttons_values(current_buttons_vals)

            # axes
            current_axes_vals = [data[i] for i in range(12, 14)]
            if self.buttons['LeftPad_Touch'].current_value is True:  # LeftPad
                 current_axes_vals += [(0, 0)] + [tuple(SteamController.to_int16(data[i], data[i+1]) for i in range(17, 21, 2))]
            else:  # LeftStick
                current_axes_vals += [tuple(SteamController.to_int16(data[i], data[i+1]) for i in range(17, 21, 2))] + [(0, 0)]
            current_axes_vals += [tuple(SteamController.to_int16(data[i], data[i+1]) for i in range(21, 25, 2))]     
            self._update_axes_values(current_axes_vals)

        elif data[3] == 3:  # woken up
            pass
        elif data[3] == 4:  # is sleeping
            pass
        else:
            assert False, "Unknown state"

    def _update_buttons_values(self, values):
        for (button, value) in zip(self.buttons_names, values):
            self.buttons[button].update_value(value)

    def _update_axes_values(self, values):
        for (axis, value) in zip(self.axes_names, values):
            self.axes[axis].update_value(value)

    @staticmethod
    def to_bool_array(byte):
        """Convert a byte to list of bools.

        Args:
            byte (int): Byte to be converted.

        Returns:
            list: List of bools.
        """

        return [bool(byte & (1 << i)) for i in range(8)]

    @staticmethod
    def to_int16(low, high):
        """Convert two bytes to int16.

        Args:
            low (int): Lower byte.
            high (int): Higher byte.

        Returns:
            int: The int16 representation of two input bytes.
        """

        return int.from_bytes(
            bytes([low, high]), byteorder='little', signed=True)


if __name__ == "__main__":

    class MySteamController(SteamController):
        """Example SteamController class implementation."""

        def __init__(self):
            super().__init__()
            self.buttons['RightTrigger'].event = lambda current_value, previous_value: print("RightTrigger button: {}, {}".format(current_value, previous_value))

            self.axes['LeftTrigger'].event = self.LeftTriggerAxisEvent

        @staticmethod
        def LeftTriggerAxisEvent(current_value, previous_value):
            print("LeftTriggerAxisEvent: {}, {}".format(
                current_value, previous_value))

    controller = MySteamController()
    controller.open()
