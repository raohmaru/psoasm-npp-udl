from __future__ import print_function
import sys
import getopt
import os, os.path
import re
import io

__author__  = "Thomas Neubert, Raohmaru"
__version__ = "1.2.0"

class Statement:
    """
    Statement containing the opcode, an argument list and an optional label.

    Attributes:
        label (int):   The function label. -1 if no label was defined.
        opcode (str):  The pasm opcode.
        params (list): The opcode argument list.
    """
    def __init__(self, opcode, params=[], label=-1):
        self.label = label
        self.opcode = opcode

        if not params:
            self.params = []
        else:
            self.params = params

    def to_string(self):
        """
        Returns a qedit, import friendly line of code.
        """
        stmt_str  = ''
        label_str = ''
        
        if self.label >= 0:
            label_str = '{}:'.format(self.label)

        stmt_str = '{:8}{} '.format(label_str, self.opcode)
        for i in range(len(self.params)):
            if i > 0:
                stmt_str += ", {}".format(self.params[i])
            else:
                stmt_str += "{}".format(self.params[i])

        return stmt_str


class PasmSyntaxError(Exception):
    """
    PASM Syntax Error exception.

    Attributes:
        msg (str):      The syntax error message.
        line_str (str): The code line.
        line_num (int): The code line number in the parsed text file.
        line_pos (int): The code line position for the syntax error.
    """
    def __init__(self, msg, line_str, line_num, line_pos):
        self.msg = msg
        self.line_str = line_str
        self.line_num = line_num
        self.line_pos = line_pos

    def print_error(self):
        """
        Print the syntax error message, the code line were the syntax error
        occured and mark the position.
        """
        print(self.msg)
        print(self.line_str)
        print(' '*self.line_pos + '^')


def read(line_str, line_pos, pattern='[0-9a-zA-Z_:?!><=&]'):
    """
    Read all tokens from a code line matching specific characters,
    starting at a specified position.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        pattern (str):  Regular expression for a single character. All matching
                        characters will be read.

    Returns:
        literal (str):  The literal that was read, including only characters
                        that were defined in the pattern argument.
        line_pos (int): The updated line position.
    """
    length  = len(line_str)
    literal = ''
    while line_pos < length and re.match(pattern, line_str[line_pos]):
        literal  += line_str[line_pos]
        line_pos += 1
    return literal, line_pos


def r_label(line_str, line_pos, line_num):
    """
    Read a label. Every label must be a valid number 0..65535.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        label (int):    The label that was read.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If the label is not a valid number.
    """
    label, line_pos_new = read(line_str, line_pos, '[0-9]')
    
    if not label.isdigit():
        msg = _text['error_label_1'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    label = int(label)
    if label > 0xFFFF:
        msg = _text['error_label_2'].format(line_num, line_pos, label)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    return label, line_pos_new


def r_register(line_str, line_pos, line_num):
    """
    Read a register. All registers must start with a R, followed by a
    number 0..255.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        register (str): The register that was read.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If the register is not valid or doesn't exist.
    """
    register, line_pos_new = read(line_str, line_pos, '[^\s,/]')
    reg_num = -1

    if not re.match('^R(0|[1-9][0-9]{0,2})$', register, re.IGNORECASE):
        msg = _text['error_register_1'].format(line_num, line_pos, register)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    reg_num = re.findall('^R([0-9]{1,3})$', register, re.IGNORECASE)[0]
    reg_num = int(reg_num)
    if reg_num > 0xFF:
        msg = _text['error_register_2'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    return register, line_pos_new


def r_byte(line_str, line_pos, line_num, length=1, hex_input=False):
    """
    Read one or more bytes in hex format.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.
        length (int):   Number of bytes to read. This defaults to just one byte.

    Returns:
        byte_str (str): The byte string.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If read byte(s) are not in hex format or
                         exceed the byte length argument.
    """
    byte_str, line_pos_new = read(line_str, line_pos, '[^\s,/]')
    pattern = '^[0-9a-f]{{1,{}}}$'.format(length*2)
    is_hex = hex_input
    has_sign = False
    
    # Checks if the value is in hex format (it starts with 0x, 0 or contains A-F)
    if byte_str[:2] == '0x':
        is_hex = True
        byte_str = byte_str[2:]
    elif byte_str[0] == '0' or re.search('[A-F]', byte_str, re.IGNORECASE):
        is_hex = True
        
    # Check if the value is signed (has a - and therefore is not an hex value)
    if byte_str[0] == '-':
        has_sign = True
        byte_str = byte_str[1:]

    if not re.match(pattern, byte_str, re.IGNORECASE):
        msg = _text['error_byte'].format(line_num, line_pos, _byte_types[length])
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
    
    if not is_hex:
         # Transform integers into hex
         if has_sign:
             # Transform negative integers into hex
             byte_str = int(0xFFFFFFFF) - int(byte_str) + 1  # -1 == FFFFFFFF
         byte_str = hex(int(byte_str))[2:]
         # Remove 'L' character (Python adds it for larger numbers)
         if byte_str[-1] == 'L':
             byte_str = byte_str[:-1]
    
    # format uppercase bytes and leading zeros
    byte_str = byte_str.upper()
    byte_str = '0'*(length*2-len(byte_str)) + byte_str
        

    return byte_str, line_pos_new


def r_word(line_str, line_pos, line_num):
    """
    Read 2 bytes in hex format.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        byte_str (str): 2 bytes.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If read bytes are not in hex format or
                         more than 2 Bytes where found.
    """
    return r_byte(line_str, line_pos, line_num, 2)


def r_dword(line_str, line_pos, line_num):
    """
    Read 4 bytes in hex format.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        byte_str (str): 4 bytes.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If read bytes are not in hex format or
                         more than 4 Bytes where found.
    """
    return r_byte(line_str, line_pos, line_num, 4)


def r_float(line_str, line_pos, line_num):
    """
    Reads value as a float number.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        float_str (str)
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If read bytes are not a valid float number.
    """
    byte_str, line_pos_new = read(line_str, line_pos, '[^\s,/]')
    pattern = '^-?[\d\.]+$'

    if not re.match(pattern, byte_str, re.IGNORECASE):
        msg = _text['error_float'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
        
    return byte_str, line_pos_new


def r_data(line_str, line_pos, line_num):
    """
    Read byte data in hex format (AA BB CC DD ...).

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        data_str (str): The data string (AA BB CC DD ...).
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If read bytes are not in hex format or not separated
                         with one or more spaces.
    """
    data_list = []
    data_str  = ''
    length = len(line_str)

    while line_pos < length and \
          re.match('[0-9a-f]', line_str[line_pos], re.IGNORECASE):
        byte, line_pos = r_byte(line_str, line_pos, line_num, hex_input=True)
        data_list.append(byte)
        line_pos = skip_spaces(line_str, line_pos)

    # TODO need to check if data list is too long? qedit uses 17 Bytes per line

    if not data_list:
        msg = _text['error_data'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    data_str = data_list[0]
    for d in data_list[1:]:
        data_str += ' {}'.format(d)
    
    return data_str, line_pos


def r_string(line_str, line_pos, line_num):
    """
    Read string. A string needs to start and end with single or double quotes.
    If single quotes are used, single quotes inside that string must be
    escaped with a backslash. If double quotes are used, double quotes must
    be escaped.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        string (str):   The string in a qedit import friendly format.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If an invalid string format was found.
    """
    length    = len(line_str)
    delimiter = None
    string    = "'"
    
    if line_pos >= length:
        msg = _text['error_string_1'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    if re.match('["\']', line_str[line_pos]):
        delimiter = line_str[line_pos]
        line_pos += 1
    else:
        msg = _text['error_string_1'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
                
    add_char = True
    while add_char:
        if line_pos >= length:
            # string has no end
            msg = _text['error_string_2'].format(line_num, line_pos)
            raise PasmSyntaxError(msg, line_str, line_num, line_pos)

        if line_str[line_pos] == delimiter:
            # end of string reached
            add_char = False
        elif line_str[line_pos] == '\\' and \
             line_pos+1 < length and \
             line_str[line_pos+1] == delimiter:
            # handle escaped delimiter
                string   += delimiter
                line_pos += 1
        else:
            string += line_str[line_pos]
        
        line_pos += 1

    string += "'"
    
    return string, line_pos


def r_array(line_str, line_pos, line_num):
    """
    Read an array of numbers.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        array (str):    The number array as a string.
        line_pos (int): The updated line position.

    Raises:
        PasmSyntaxError: If the array length (first value) is not equal to the
                         amount of elements.
    """
    array_str, line_pos_new = read(line_str, line_pos, '[^\s,/]')
    array = None
    count = 0

    if not re.match('^[1-9][0-9]*(:[0-9]+)+$', array_str):
        msg = _text['error_array'].format(line_num, line_pos, array_str)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    array = array_str.split(':')
    count = int(array[0])

    # check element count
    if count != len(array)-1:
        msg = _text['error_array_count'].format(line_num, line_pos, count)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    return array_str, line_pos_new


def r_array_label(line_str, line_pos, line_num):
    """
    Read an array of labels.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        label_array (str): The label array as a string.
        line_pos (int):    The updated line position.

    Raises:
        PasmSyntaxError: If the array length (first value) is not equal to the
                         amount of elements.
                         If one of the label elements is invalid.
    """
    label_array_str, line_pos = r_array(line_str, line_pos, line_num)
    label_array = label_array_str.split(':')

    # check valid labels
    for lab in label_array[1:]:
        if int(lab) > 0xFFFF:
            msg = _text['error_label_2'].format(line_num, line_pos, lab)
            raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    return label_array_str, line_pos
    

def r_array_register(line_str, line_pos, line_num):
    """
    Read an array of registers.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        label_array (str): The label array as a string.
        line_pos (int):    The updated line position.

    Raises:
        PasmSyntaxError: If the array length (first value) is not equal to the
                         amount of elements.
                         If one of the register elements is invalid.
    """
    reg_array_str, line_pos = r_array(line_str, line_pos, line_num)
    reg_array = reg_array_str.split(':')

    # check valid registers
    for reg in reg_array[1:]:
        if int(reg) > 0xFF:
            msg = _text['error_register_2'].format(line_num, line_pos, reg)
            raise PasmSyntaxError(msg, line_str, line_num, line_pos)

    return reg_array_str, line_pos


def r_separator(line_str, line_pos, line_num):
    """
    Read an opcode argument separator ','.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        line_num (int): The code line number in the parsed text file.

    Returns:
        line_pos (int):    The updated line position.

    Raises:
        PasmSyntaxError: If no separator was found.
    """
    length = len(line_str)
    
    if line_pos >= length or line_str[line_pos] != ',':
        msg = _text['error_separator'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
    
    return line_pos + 1


def skip_spaces(line_str, line_pos):
    """
    Skip all white spaces.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.

    Returns:
        line_pos (int): The updated line position.
    """
    return read(line_str, line_pos, '[\s]')[1]


def skip_comment(line_str, line_pos, line_num):
    """
    Skip all comments.

    Args:
        line_str (str): The code line.
        line_pos (int): The code line position to start reading.
        
    Raises:
        PasmSyntaxError: If comment doesn't start with '//'.
    """
    length = len(line_str)
    token = line_str[line_pos:line_pos+2]

    if (line_pos+1) >= length or \
       token != '//' and token != '/*':
        msg = _text['error_comment'].format(line_num, line_pos)
        raise PasmSyntaxError(msg, line_str, line_num, line_pos)


def main(argv=[]):
    # flags
    # generate qedit compliant pasm file
    qedit      = False
    # generate dummy labels with a simple ret statement for all missing labels
    fix_labels = False
    # the parsed statement list
    stmt_list  = []

    # all label definitions and label jumps
    label_defs  = set()
    label_jumps = set()

    # input and output file names
    f_name_in  = None
    f_name_out = None
    
    # indicates that the line might be inisde a multiline comment (/* ... */)
    multiline_comment = False

    # read options
    opt_list, args = getopt.getopt(argv, 'qf')
    for opt, value in opt_list:
        if opt == '-q':   qedit      = True
        elif opt == '-f': fix_labels = True

    # set pasm file argument, exit if nothing was set
    if args:
        f_name_in  = os.path.abspath(args[0])
        f_name_out = 'qe_' + os.path.basename(f_name_in)
        f_name_out = os.path.join(os.path.dirname(f_name_in), f_name_out)
    else:
        print(_text['pasm_arg_missing'])
        print()
        print(_text['usage'])
        return

    # check if pasm file exists, exit if not
    if not os.path.exists(f_name_in):
        print(_text['file_not_found'].format(f_name_in))
        return

    # start parsing line by line...
    with io.open(f_name_in, mode='r', encoding='utf16') as f_in:
        try:
            line_num = 0
            for line_str in f_in:
                length   = len(line_str)
                line_pos = 0
                line_num = line_num + 1
                label    = -1
                stmt     = None
                literal  = None

                # skip leading spaces and discard empty lines
                line_pos = skip_spaces(line_str, line_pos)
                if line_pos >= length:
                    continue
                  
                # handles multiline comment
                if multiline_comment:
                    if line_str[line_pos:line_pos+2] == '*/':
                        multiline_comment = False;
                    continue

                # discard comments
                if line_str[line_pos] == '/':
                    skip_comment(line_str, line_pos, line_num)
                    
                    # starts multiline comment?
                    if line_str[line_pos:line_pos+2] == '/*':
                        multiline_comment = True
                    continue

                # check if there is a label definition
                if re.match('[0-9]', line_str[line_pos]):
                    label, line_pos = r_label(line_str, line_pos, line_num)

                    if label >= 0 and label in label_defs:
                        msg = _text['error_label_4'].format(line_num, line_pos, label)
                        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
                    label_defs.add(label)
                    
                    if line_pos < length and line_str[line_pos] == ':':
                        # label definition complete
                        line_pos += 1
                    else:
                        # missing ':' after label definition
                        msg = _text['error_label_3'].format(line_num, line_pos)
                        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
                    
                    line_pos = skip_spaces(line_str, line_pos)

                if line_pos >= length:
                    # something went wrong, was expecting opcode
                    msg = _text['error_opcode_1'].format(line_num, line_pos)
                    raise PasmSyntaxError(msg, line_str, line_num, line_pos)

                # parse opcode
                if re.match('[^\s]', line_str[line_pos]):
                    opcode, line_pos = read(line_str, line_pos, '[^\s]')

                    if opcode in _opcode_alias.keys():
                        opcode = _opcode_alias[opcode]
                    
                    if not opcode in _opcode_dict.keys():
                        # opcode doesn't exist
                        msg = _text['error_opcode_2'].format(line_num, line_pos, opcode)
                        raise PasmSyntaxError(msg, line_str, line_num, line_pos)
                    stmt = Statement(opcode)
                    stmt.label = label

                    line_pos = skip_spaces(line_str, line_pos)

                    # parse statement parameters
                    opcode_param_def = _opcode_dict[opcode]
                    i = 1
                    for opd in opcode_param_def:
                        literal, line_pos = opd(line_str, line_pos, line_num)
                        stmt.params.append(literal)

                        if i < len(opcode_param_def):
                            line_pos = skip_spaces(line_str, line_pos)
                            line_pos = r_separator(line_str, line_pos, line_num)
                            line_pos = skip_spaces(line_str, line_pos)

                        i += 1

                        if opd == r_label:
                            label_jumps.add(literal)
                        elif opd == r_array_label:
                            label_list = literal.split(':')[1:]
                            for l in label_list:
                                label_jumps.add(int(l))

                    stmt_list.append(stmt)
                    
                else:
                    # something went wrong, was expecting opcode
                    msg = _text['error_opcode_1'].format(line_num, line_pos)
                    raise PasmSyntaxError(msg, line_str, line_num, line_pos)

                # skip spaces
                line_pos = skip_spaces(line_str, line_pos)

                # discard comments
                if line_pos < length and line_str[line_pos] == '/':
                    skip_comment(line_str, line_pos, line_num)

        except PasmSyntaxError as pse:
            pse.print_error()
            return

        # check if label jumps have a target
        for lab in label_jumps:
            if not lab in label_defs:
                print(_text['warn_label'].format(lab))
                if fix_labels:
                    print(_text['warn_label_add'].format(lab))
                    stmt_list.append(Statement('ret', [], lab))

        # convert to qedit readable format
        with io.open(f_name_out, 'w', encoding='utf-16') as f_out:
            for stmt in stmt_list:
                print(unicode(stmt.to_string()), file=f_out)


# All text...
_byte_types = { 1: 'BYTE', 2: 'WORD', 4: 'DWORD' }
_text = {
    'usage':
        "python pasm.py [options] <pasm_file>\n" \
        "\n" \
        "Arguments:\n" \
        " <pasm_file>   Path to the pasm file.\n" \
        "\n" \
        "Options:\n" \
        " -q            Compress pasm file for qedit import. Removes all\n" \
        "               comments and empty lines and writes a new pasm file\n" \
        "               with a 'qe_' prefix.\n"\
        " -f            Add dummy entries for any missing labels. Those will\n"\
        "               contain a simple ret statement.",
        
     'pasm_arg_missing':
        "No PASM file defined.",
     'file_not_found':
        "File '{}' not found.",

     'error_label_1':
        "Error line {}, position {}: Invalid label format, must be a number.",
     'error_label_2':
        "Error line {}, position {}: Invalid label '{}', must be a number 0..65535.",
     'error_label_3':
        "Error line {}, position {}: Invalid label definition, was expecting ':'.",
      'error_label_4':
        "Error line {}, position {}: Label '{}' was already defined.",
      'warn_label':
         "Warning: Label jump to '{}' has no target.",
      'warn_label_add':
         "Adding dummy entry for label '{}'.",
        
     'error_opcode_1':
        "Error line {}, position {}: Opcode expected.",
     'error_opcode_2':
        "Error line {}, position {}: Opcode '{}' doesn't exist.",

     'error_comment':
        "Error line {}, position {}: Start comments with '//' or '/*'.",

     'error_register_1':
        "Error line {}, position {}: Invalid register format '{}'. Needs to be\nR<number> where number is 0-255.",
     'error_register_2':
        "Error line {}, position {}: Only registers 0-255 supported.",

     'error_byte':
        "Error line {}, position {}: Invalid {} format.",

     'error_float':
        "Error line {}, position {}: Invalid float number format.",

     'error_array':
        "Error line {}, position {}: Invalid array format '{}'.\nMust be 'count:num1:num2:num3:...'",
     'error_array_count':
        "Error line {}, position {}: Invalid array format, {} elements are required.",

     'error_string_1':
        "Error line {}, position {}: Was expecting String.",
     'error_string_2':
        "Error line {}, position {}: String has no closing quote.",

     'error_separator':
        "Error line {}, position {}: Was expecting separator ','.",
    }

# Opcode aliases.
# If one of those is found, it will be replaced with the qedit equivalent.
_opcode_alias = {
    'msg': 'message',
    'msg_add': 'add_msg',
    'msg_end': 'mesend',
    'win_msg': 'window_msg',
    'win_end': 'winend',
    'disable_mainmenu': 'disable_mainmen',
    'modi': 'unknownEA',
    'players_in_range': 'unknownF883',
    'disp_chl_retry_menu': 'disp_chl_retry_mnu',
    'set_slot_targetable': 'unknownF8CB',
    'item_delete2': 'item_delete21CF',
    #'BB_exchange_SLT': 'BB_exchange_SL'
}

# Opcode dictionary, containing all opcodes and their parameters.
_opcode_dict = {
    'nop': [],
    'ret': [],
    'sync': [],
    'exit': [r_dword],
    'thread': [r_label],
    'va_start': [],
    'va_end': [],
    'va_call': [r_label],
    'let': [r_register, r_register],
    'leti': [r_register, r_dword],
    'set': [r_register],
    'clear': [r_register],
    'rev': [r_register],
    'gset': [r_word],
    'gclear': [r_word],
    'grev': [r_word],
    'glet': [r_word],
    'gget': [r_word, r_register],
    'add': [r_register, r_register],
    'addi': [r_register, r_dword],
    'sub': [r_register, r_register],
    'subi': [r_register, r_dword],
    'mul': [r_register, r_register],
    'muli': [r_register, r_dword],
    'div': [r_register, r_register],
    'divi': [r_register, r_dword],
    'and': [r_register, r_register],
    'andi': [r_register, r_dword],
    'or': [r_register, r_register],
    'ori': [r_register, r_dword],
    'xor': [r_register, r_register],
    'xori': [r_register, r_dword],
    'mod': [r_register, r_register],
    'modi': [r_register, r_dword],
    'jmp': [r_label],
    'call': [r_label],
    'jmp_on': [r_label, r_array_register],
    'jmp_off': [r_label, r_array_register],
    'jmp_=': [r_register, r_register, r_label],
    'jmpi_=': [r_register, r_dword, r_label],
    'jmp_!=': [r_register, r_register, r_label],
    'jmpi_!=': [r_register, r_dword, r_label],
    'ujmp_>': [r_register, r_register, r_label],
    'ujmpi_>': [r_register, r_dword, r_label],
    'jmp_>': [r_register, r_register, r_label],
    'jmpi_>': [r_register, r_dword, r_label],
    'ujmp_<': [r_register, r_register, r_label],
    'ujmpi_<': [r_register, r_dword, r_label],
    'jmp_<': [r_register, r_register, r_label],
    'jmpi_<': [r_register, r_dword, r_label],
    'ujmp_>=': [r_register, r_register, r_label],
    'ujmpi_>=': [r_register, r_dword, r_label],
    'jmp_>=': [r_register, r_register, r_label],
    'jmpi_>=': [r_register, r_dword, r_label],
    'ujmp_<=': [r_register, r_register, r_label],
    'ujmpi_<=': [r_register, r_dword, r_label],
    'jmp_<=': [r_register, r_register, r_label],
    'jmpi_<=': [r_register, r_dword, r_label],
    'switch_jmp': [r_register, r_array_label],
    'switch_call': [r_register, r_array_label],
    'stack_push': [r_register],
    'stack_pop': [r_register],
    'stack_pushm': [r_register, r_dword],
    'stack_popm': [r_register, r_dword],
    'arg_pushr': [r_register],
    'arg_pushl': [r_dword],
    'arg_pushb': [r_register],
    'arg_pushw': [r_word],
    'arg_pushs': [r_string],
    'unknown4F': [r_register, r_register],
    'message': [r_dword, r_string],
    'list': [r_register, r_string],
    'fadein': [],
    'fadeout': [],
    'se': [r_dword],
    'bgm': [r_dword],
    'enable': [r_dword],
    'disable': [r_dword],
    'window_msg': [r_string],
    'add_msg': [r_string],
    'mesend': [],
    'gettime': [r_register],
    'winend': [],
    'npc_crt_V1': [r_register, r_dword],
    'npc_crt_V3': [r_register],
    'npc_stop': [r_dword],
    'npc_play': [r_dword],
    'npc_kill': [r_dword],
    'npc_nont': [],
    'npc_talk': [],
    'npc_crp_V1': [r_register, r_dword],
    'npc_crp_V3': [r_register],
    'create_pipe': [r_dword],
    'p_hpstat_V1': [r_register, r_dword],
    'p_hpstat_V3': [r_register, r_dword],
    'p_dead_V1': [r_register, r_dword],
    'p_dead_V3': [r_register, r_dword],
    'p_disablewarp': [],
    'p_enablewarp': [],
    'p_move_v1': [r_register, r_dword],
    'p_move_V3': [r_register],
    'p_look': [r_dword],
    'p_action_disable': [],
    'p_action_enable': [],
    'disable_movement1': [r_dword],
    'enable_movement1': [r_dword],
    'p_noncol': [],
    'p_col': [],
    'p_setpos': [r_dword, r_register],
    'p_return_guild': [],
    'p_talk_guild': [r_dword],
    'npc_talk_pl_V1': [r_register, r_dword],
    'npc_talk_pl_V3': [r_register],
    'npc_talk_kill': [r_dword],
    'npc_crtpk_V1': [r_register, r_dword],
    'npc_crtpk_V3': [r_register],
    'npc_crppk_V1': [r_register, r_dword],
    'npc_crppk_V3': [r_register],
    'npc_crptalk_v1': [r_register, r_dword],
    'npc_crptalk_V3': [r_register],
    'p_look_at': [r_dword, r_dword],
    'npc_crp_id_V1': [r_register, r_dword],
    'npc_crp_id_v3': [r_register],
    'cam_quake': [],
    'cam_adj': [],
    'cam_zmin': [],
    'cam_zmout': [],
    'cam_pan_V1': [r_register, r_dword],
    'cam_pan_V3': [r_register],
    'game_lev_super': [],
    'game_lev_reset': [],
    'pos_pipe_V1': [r_register, r_dword],
    'pos_pipe_V3': [r_register],
    'if_zone_clear': [r_register, r_register],
    'chk_ene_num': [r_register],
    'unhide_obj': [r_register],
    'unhide_ene': [r_register],
    'at_coords_call': [r_register],
    'at_coords_talk': [r_register],
    'col_npcin': [r_register],
    'col_npcinr': [r_register],
    'switch_on': [r_dword],
    'switch_off': [r_dword],
    'playbgm_epi': [r_dword],
    'set_mainwarp': [r_dword],
    'set_obj_param': [r_register, r_register],
    'set_floor_handler': [r_dword, r_label],
    'clr_floor_handler': [r_dword],
    'col_plinaw': [r_register],
    'hud_hide': [],
    'hud_show': [],
    'cine_enable': [],
    'cine_disable': [],
    'set_qt_failure': [r_label],
    'set_qt_success': [r_label],
    'clr_qt_failure': [],
    'clr_qt_success': [],
    'set_qt_cancel': [r_label],
    'clr_qt_cancel': [],
    'pl_walk_V1': [r_register, r_dword],
    'pl_walk_V3': [r_register],
    'pl_add_meseta': [r_dword, r_dword],
    'thread_stg': [r_label],
    'del_obj_param': [r_register],
    'item_create': [r_register, r_register],
    'item_create2': [r_register, r_register],
    'item_delete': [r_register, r_register],
    'item_delete2': [r_register, r_register],
    'item_check': [r_register, r_register],
    'setevt': [r_dword],
    'get_difflvl': [r_register],
    'set_qt_exit': [r_label],
    'clr_qt_exit': [],
    'particle_V1': [r_register, r_dword],
    'particle_V3': [r_register],
    'npc_text': [r_dword, r_string],
    'npc_chkwarp': [],
    'pl_pkoff': [],
    'map_designate': [r_register],
    'masterkey_on': [],
    'masterkey_off': [],
    'window_time': [],
    'winend_time': [],
    'winset_time': [r_register],
    'getmtime': [r_register],
    'set_quest_board_handler': [r_dword, r_label, r_string],
    'clear_quest_board_handler': [r_dword],
    'particle_id_V1': [r_register, r_dword],
    'particle_id_V3': [r_register],
    'npc_crptalk_id_V1': [r_register, r_dword],
    'npc_crptalk_id_V3': [r_register],
    'npc_lang_clean': [],
    'pl_pkon': [],
    'pl_chk_item2': [r_register, r_register],
    'enable_mainmenu': [],
    'disable_mainmen': [],
    'start_battlebgm': [],
    'end_battlebgm': [],
    'disp_msg_qb': [r_string],
    'close_msg_qb': [],
    'set_eventflag_v1': [r_register, r_dword],
    'set_eventflag_v3': [r_dword, r_dword],
    'sync_leti': [r_register, r_dword],
    'set_returnhunter': [],
    'set_returncity': [],
    'load_pvr': [],
    'load_midi': [],
    'npc_param_V1': [r_register, r_dword],
    'npc_param_V3': [r_register, r_dword],
    'pad_dragon': [],
    'clear_mainwarp': [r_dword],
    'pcam_param_V1': [r_register],
    'pcam_param_V3': [r_register],
    'start_setevt_v1': [r_register, r_dword],
    'start_setevt_v3': [r_register, r_dword],
    'warp_on': [],
    'warp_off': [],
    'get_slotnumber': [r_register],
    'get_servernumber': [r_register],
    'set_eventflag2': [r_dword, r_register],
    'res': [r_register, r_register],
    'unknownEA': [r_register, r_dword],
    'enable_bgmctrl': [r_dword],
    'sw_send': [r_register],
    'create_bgmctrl': [],
    'pl_add_meseta2': [r_dword],
    'sync_let': [r_register, r_register],
    'sync_register': [r_register, r_dword],
    'send_regwork': [r_register, r_dword],
    'leti_fixed_camera_V1': [r_register],
    'leti_fixed_camera_V3': [r_register],
    'unknownF8': [r_register],
    'get_gc_number': [],
    'unknownFB': [r_label],
    'set_chat_callback?': [r_register, r_string],
    'get_difflvl2': [r_register],
    'get_number_of_player1': [r_register],
    'get_coord_of_player': [r_register, r_register],
    'unknownF80B': [],
    'unknownF80C': [],
    'map_designate_ex': [r_register],
    'unknownF80E': [r_dword],
    'unknownF80F': [r_dword],
    'ba_initial_floor': [r_dword],
    'set_ba_rules': [],
    'unknownF812': [r_dword],
    'unknownF813': [r_dword],
    'unknownF814': [r_dword],
    'unknownF815': [r_dword],
    'unknownF816': [r_dword],
    'unknownF817': [r_dword],
    'unknownF818': [r_dword],
    'unknownF819': [r_dword],
    'unknownF81A': [r_dword],
    'unknownF81B': [r_dword],
    'ba_disp_msg': [r_string],
    'death_lvl_up': [r_dword],
    'death_tech_lvl_up': [r_dword],
    'cmode_stage': [r_dword],
    'unknownF823': [r_dword],
    'unknownF824': [r_dword],
    'exp_multiplication': [r_register],
    'exp_division?': [r_register],
    'get_user_is_dead?': [r_register],
    'go_floor': [r_register, r_register],
    'unlock_door2': [r_dword, r_dword],
    'lock_door2': [r_dword, r_dword],
    'if_switch_not_pressed': [r_register],
    'if_switch_pressed': [r_register],
    'unknownF82F': [r_dword, r_dword],
    'control_dragon': [r_register],
    'release_dragon': [],
    'shrink': [r_register],
    'unshrink': [r_register],
    'display_clock2?': [r_register],
    'unknownF83D': [r_dword],
    'delete_area_title?': [r_dword],
    'load_npc_data': [],
    'get_npc_data': [r_label],
    'give_damage_score': [r_register],
    'take_damage_score': [r_register],
    'unk_score_F84A': [r_register],
    'unk_score_F84B': [r_register],
    'kill_score': [r_register],
    'death_score': [r_register],
    'unk_score_F84E': [r_register],
    'enemy_death_score': [r_register],
    'meseta_score': [r_register],
    'unknownF851': [r_register],
    'unknownF852': [r_dword],
    'reverse_warps': [],
    'unreverse_warps': [],
    'set_ult_map': [],
    'unset_ult_map': [],
    'set_area_title': [r_string],
    'unknownF858': [],
    'equip_item_v2': [r_register],
    'equip_item_v3': [r_register],
    'unequip_item_V2': [r_register, r_dword],
    'unequip_item_V3': [r_dword, r_dword],
    'unknownF85E': [r_dword],
    'unknownF85F': [r_dword],
    'unknownF860': [],
    'unknownF861': [r_dword],
    'cmode_rank': [r_dword, r_string],
    'award_item_name?': [],
    'award_item_select?': [],
    'award_item_give_to?': [r_register],
    'unknownF868': [r_register, r_register],
    'unknownF869': [r_register, r_register],
    'item_create_cmode': [r_register, r_register],
    'unknownF86B': [r_register],
    'award_item_ok?': [r_register],
    'unknownF86D': [],
    'unknownF86E': [],
    'ba_set_lives': [r_dword],
    'ba_set_tech_lvl': [r_dword],
    'ba_set_lvl': [r_dword],
    'ba_set_time_limit': [r_dword],
    'boss_is_dead?': [r_register],
    'enable_techs': [r_register],
    'disable_techs': [r_register],
    'get_gender': [r_register, r_register],
    'get_chara_class': [r_register, r_register],
    'take_slot_meseta': [r_register, r_register],
    'guildcard_flag': [r_register, r_register],
    'unknownF880': [r_register],
    'get_pl_name?': [r_register],
    'unknownF883': [r_register, r_register],
    'ba_close_msg': [],
    'get_player_status': [r_register, r_register],
    'send_mail': [r_register, r_string],
    'online_check': [r_register],
    'chl_set_timerecord?': [r_register],
    'chl_get_timerecord?': [r_register],
    'unknownF88F': [r_register],
    'unknownF890': [],
    'load_enemy_data': [r_dword],
    'get_physical_data': [r_label],
    'get_attack_data': [r_label],
    'get_resist_data': [r_label],
    'get_movement_data': [r_label],
    'shift_left': [r_register, r_register],
    'shift_right': [r_register, r_register],
    'get_random': [r_register, r_register],
    'disp_chl_retry_mnu': [r_register],
    'chl_reverser?': [],
    'unknownF89E': [r_dword],
    'unknownF89F': [r_register],
    'unknownF8A0': [],
    'unknownF8A1': [],
    'unknownF8A8': [r_dword],
    'unknownF8A9': [r_register],
    'get_number_of_player2': [r_register],
    'unknownF8B8': [],
    'chl_recovery?': [],
    'set_episode': [r_dword],
    'file_dl_req': [r_dword, r_string],
    'get_dl_status': [r_register],
    'gba_unknown4?': [],
    'get_gba_state?': [r_register],
    'unknownF8C4': [r_register],
    'unknownF8C5': [r_register],
    'QEXIT': [],
    'use_animation': [r_register, r_register],
    'stop_animation': [r_register],
    'run_to_coord': [r_register, r_register],
    'set_slot_invincible': [r_register, r_register],
    'unknownF8CB': [r_register],
    'set_slot_poison': [r_register],
    'set_slot_paralyse': [r_register],
    'set_slot_shock': [r_register],
    'set_slot_freeze': [r_register],
    'set_slot_slow': [r_register],
    'set_slot_confuse': [r_register],
    'set_slot_shifta': [r_register],
    'set_slot_deband': [r_register],
    'set_slot_jellen': [r_register],
    'set_slot_zalure': [r_register],
    'fleti_fixed_camera': [r_register],
    'fleti_locked_camera': [r_dword, r_register],
    'default_camera_pos1': [],
    'default_camera_pos2': [],
    'set_motion_blur': [],
    'set_screen_b&w': [],
    'unknownF8DB': [r_dword, r_dword, r_dword, r_dword, r_register, r_label],
    'NPC_action_string': [r_register, r_register, r_label],
    'get_pad_cond': [r_register, r_register],
    'get_button_cond': [r_register, r_register],
    'freeze_enemies': [],
    'unfreeze_enemies': [],
    'freeze_everything': [],
    'unfreeze_everything': [],
    'restore_hp': [r_register],
    'restore_tp': [r_register],
    'close_chat_bubble': [r_register],
    'unknownF8E6': [r_register, r_register],
    'unknownF8E7': [r_register, r_register],
    'unknownF8E8': [r_register, r_register],
    'unknownF8E9': [r_register, r_register],
    'unknownF8EA': [r_register, r_register],
    'unknownF8EB': [r_register, r_register],
    'unknownF8EC': [r_register, r_register],
    'animation_check': [r_register, r_register],
    'call_image_data': [r_dword, r_label],
    'unknownF8EF': [],
    'turn_off_bgm_p2': [],
    'turn_on_bgm_p2': [],
    'load_unk_data': [r_dword, r_dword, r_dword, r_dword, r_register, r_label],
    'particle2': [r_register, r_dword, r_float],
    'dec2float': [r_register, r_register],
    'float2dec': [r_register, r_register],
    'flet': [r_register, r_register],
    'fleti': [r_register, r_float],
    'fadd': [r_register, r_register],
    'faddi': [r_register, r_float],
    'fsub': [r_register, r_register],
    'fsubi': [r_register, r_float],
    'fmul': [r_register, r_register],
    'fmuli': [r_register, r_float],
    'fdiv': [r_register, r_register],
    'fdivi': [r_register, r_float],
    'get_unknown_count?': [r_dword, r_register],
    'get_stackable_item_count': [r_register, r_register],
    'freeze_and_hide_equip': [],
    'thaw_and_show_equip': [],
    'set_paletteX_callback': [r_register, r_label],
    'activate_paletteX': [r_register],
    'enable_paletteX': [r_register],
    'restore_paletteX': [r_dword],
    'disable_paletteX': [r_dword],
    'get_paletteX_activated': [r_dword, r_register],
    'get_unknown_paletteX_status?': [r_dword, r_register],
    'disable_movement2': [r_register],
    'enable_movement2': [r_register],
    'get_time_played': [r_register],
    'get_guildcard_total': [r_register],
    'get_slot_meseta': [r_register],
    'get_player_level': [r_dword, r_register],
    'get_Section_ID': [r_dword, r_register],
    'get_player_hp': [r_register, r_register],
    'get_floor_number': [r_register, r_register],
    'get_coord_player_detect': [r_register, r_register],
    'global_flag': [r_dword, r_register],
    'write_global_flag': [r_dword, r_register],
    'unknownF927': [r_register, r_register],
    'floor_player_detect': [r_register],
    'disk_file?': [r_string],
    'open_pack_select': [],
    'item_select': [r_register],
    'get_item_id': [r_register],
    'color_change': [r_register, r_register, r_register, r_register, r_register],
    'send_statistic?': [r_dword, r_dword, r_dword, r_dword, r_dword, r_dword, r_dword, r_dword],
    'unknownF92F': [r_dword, r_dword],
    'chat_box': [r_dword, r_dword, r_dword, r_dword, r_dword, r_string],
    'chat_bubble': [r_dword, r_string],
    'unknownF933': [r_register],
    'scroll_text': [r_dword, r_dword, r_dword, r_dword, r_dword, r_float, r_register, r_string],
    'gba_unknown1': [],
    'gba_unknown2': [],
    'gba_unknown3': [],
    'add_damage_to?': [r_dword, r_dword],
    'item_delete21CF': [r_dword],
    'get_item_info': [r_dword, r_register],
    'item_packing1': [r_dword],
    'item_packing2': [r_dword, r_dword],
    'get_lang_setting?': [r_register],
    'prepare_statistic?': [r_dword, r_label, r_label],
    'keyword_detect': [],
    'Keyword': [r_register, r_dword, r_string],
    'get_guildcard_num': [r_dword, r_register],
    'get_wrap_status': [r_dword, r_register],
    'initial_floor': [r_dword],
    'sin': [r_register, r_dword],
    'cos': [r_register, r_dword],
    'boss_is_dead2?': [r_register],
    'unknownF94B': [r_register],
    'unknownF94C': [r_register],
    'is_there_cardbattle?': [r_register],
    'BB_p2_menu': [r_dword],
    'BB_Map_Designate': [r_byte, r_word, r_byte, r_byte],
    'BB_get_number_in_pack': [r_register],
    'BB_swap_item': [r_dword, r_dword, r_dword, r_dword, r_dword, r_dword, r_label, r_label],
    'BB_check_wrap': [r_register, r_register],
    'BB_exchange_PD_item': [r_register, r_register, r_register, r_label, r_label],
    'BB_exchange_PD_srank': [r_register, r_register, r_register, r_register, r_register, r_label, r_label],
    'BB_exchange_PD_special': [r_register, r_register, r_register, r_register, r_register, r_dword, r_label, r_label],
    'BB_exchange_PD_percent': [r_register, r_register, r_register, r_register, r_register, r_dword, r_label, r_label],
    'unknownF959': [r_dword],
    'BB_exchange_SL': [r_dword, r_register, r_label, r_label],
    'BB_exchange_PC': [],
    'BB_box_create_BP': [r_dword, r_dword, r_dword],
    'BB_exchange_PT': [r_register, r_register, r_dword, r_label, r_label],
    'unknownF960': [r_dword],
    'unknownF961': [],
    'HEX:': [r_data],
    'STR:': [r_string]
}

if __name__ == '__main__':
    main(sys.argv[1:])
