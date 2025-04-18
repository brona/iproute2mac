import subprocess
import sys
import os

# Colors
class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    CYAN = "\033[36m"

# Whether to use colors in output
use_colors = False

def set_color_output(enable=True):
    """
    Set whether to use colors in output
    
    Args:
        enable (bool): True to enable colors, False to disable
    """
    global use_colors
    use_colors = enable

def get_color_output():
    """
    Get current color output setting
    
    Returns:
        bool: True if colors are enabled, False otherwise
    """
    return use_colors

def supports_color():
    """
    Check if the terminal supports color output using tput
    
    Returns:
        bool: True if terminal supports color, False otherwise
    """
    # Check if output is a terminal
    if not sys.stdout.isatty():
        return False
    
    # Check NO_COLOR environment variable
    if os.getenv('NO_COLOR') is not None:
        return False
    
    try:
        # Use tput to check color support
        colors = int(subprocess.check_output(['tput', 'colors'], 
                                          stderr=subprocess.DEVNULL).decode().strip())
        return colors >= 8
    except (subprocess.CalledProcessError, ValueError):
        # If tput fails or returns invalid output, fall back to TERM check
        term = os.getenv('TERM', '')
        if term == 'dumb':
            return False
            
        color_terms = ['xterm', 'xterm-color', 'xterm-256color', 'linux', 
                      'screen', 'screen-256color', 'vt100', 'rxvt']
        return any(term.startswith(t) for t in color_terms)

def colorize(color, text):
    """
    Wraps text with color if colors are enabled and terminal supports it
    
    Args:
        color (str): Color code from Colors class
        text (str): Text to colorize
        
    Returns:
        str: Colorized text if colors enabled, original text otherwise
    """
    if get_color_output():
        if not hasattr(colorize, '_checked_terminal'):
            colorize._checked_terminal = True
            if not supports_color():
                perror("Warning: Your terminal does not support colors. Color output disabled.")
                set_color_output(False)
                return text
        return f"{color}{text}{Colors.RESET}"
    return text

# Helper functions
def perror(*args):
    sys.stderr.write(*args)
    sys.stderr.write("\n") 

def init_color(*argv):
    no_color = os.getenv("NO_COLOR") is not None
    
    if len(argv) > 0 and "-color".startswith(argv[0].split("=")[0]):
        color_arg = argv[0].split("=")[1] if "=" in argv[0] else "auto"
        if color_arg == "never":
            set_color_output(False)
        elif color_arg == "always":
            set_color_output(True)
        elif color_arg == "auto":
            # Enable colors if stdout is a terminal and NO_COLOR is not set
            set_color_output(sys.stdout.isatty() and not no_color)
    else:
        # Default behavior if no color argument is provided
        set_color_output(sys.stdout.isatty() and not no_color)
