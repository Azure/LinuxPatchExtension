class VirtualTerminal(object):
    class TerminalColors(object):
        SUCCESS = '\033[92m'
        WARNING = '\033[93m'
        ERROR = '\033[91m'
        HIGHLIGHT = '\033[95m'
        LOWLIGHT = '\033[96m'
        DARK = '\033[0;94m'
        RESET = '\033[0m'

    def __init__(self, enable_virtual_terminal=True):
        self.enabled = True if enable_virtual_terminal else False  # forcing boolean

    def print_success(self, message):
        if self.enabled:
            print(self.TerminalColors.SUCCESS + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_warning(self, message):
        if self.enabled:
            print(self.TerminalColors.WARNING + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_error(self, message):
        if self.enabled:
            print(self.TerminalColors.ERROR + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_highlight(self, message):
        if self.enabled:
            print(self.TerminalColors.HIGHLIGHT + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_lowlight(self, message):
        if self.enabled:
            print(self.TerminalColors.LOWLIGHT + message + self.TerminalColors.RESET)
        else:
            print(message)

    def print_dark(self, message):
        if self.enabled:
            print(self.TerminalColors.DARK + message + self.TerminalColors.RESET)
        else:
            print(message)
