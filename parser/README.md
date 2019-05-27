# Parser, Syntax Checker and Transpiler
PASM files cannot be directly imported into [QEdit](https://qedit.info/index.php?title=Main_Page) unless the format is correct (and QEdit is very picky with it). To ensure compatibility, use this parser and checker utility that will [transpile](https://en.wikipedia.org/wiki/Source-to-source_compiler) your PASM files and create a formatted file to be imported in QEdit.

## Requeriments
You need [Python](https://www.python.org/) installed on your computer in order to run the script.

For Python 3 or greater, use [pasm.py](https://raw.githubusercontent.com/raohmaru/psoasm-npp-udl/master/parser/pasm.py).  
For Python 2, use [pasm_2.7.py](https://raw.githubusercontent.com/raohmaru/psoasm-npp-udl/master/parser/pasm_2.7.py).

## Usage
To use the script, simply type in your command line/terminal:
```
python pasm.py [options] <pasm_file>
```
(If you have installed Python 2 then replace `pasm.py` with `pasm_2.7.py`.)

Options:
+ `-f` This will add any missing function labels with a simple `ret` statement. (Like: `800: ret`)

The script will remove all the comments, take care of the correct formatting for QEdit and create a new pasm file with a 'qe_' prefix.

Some syntax errors that get detected:
+ misspelled opcodes (if you use syntax highlighting, you'll already see when there's something wrong),
+ invalid opcode arguments,
+ registers that don't exist (R256...),
+ warns about missing function labels in any jump statement (this includes switch cases like `2:100:101`),
+ invalid switch case definitions like `3:100:101` (needs 3 elements, not just 2),
+ some more...

## Extended Syntax
The python script adds some enhancements to the language that will be not possible in the current PASM syntax. When a script with extended syntax (or PASM v2) is parsed, it is converted to the format compatible with QEdit and PSO (PASM v1).

### PASM v2 Features
Support for single line comments starting with `//` and multiline comments `/* ... */`.

Hexadecimal values can be expressed with the prefix `0x`. (`0x09FC8800`).

Byte, Word and DWord can be expressed as signed integer values. The parser will transform negative values into hexadecimal values (-71 -> FFFFFFB9).

Float values are allowed in the following OP codes: `particle2`, `fleti`, `faddi`, `fsubi`, `fmuli`, `fdivi`, `scroll_text`.

#### Variables
PASM v2 allows the definition of variables to store data during transcompiling time.  

Syntax:
```
variablename value
```
where `variablename` must start with `$` followed by an [identifier name](#identifier-name),  
and `value` can be any kind of value (integers, strings, registers, labels or OP codes).

Example:
```
$R_win R255
$epi1 0
$f_piooner 0x00
$qt_success 250
$win_quote 'Thank you for completing the job.<cr>Please take your reward.'

0:      set_episode $epi1
        set_floor_handler $f_piooner, 100
		set_qt_success $qt_success

300:    sync_register $R_win, 0x01

$qt_success:window_msg $win_quote
        winend
        ret
		
[ Result ]
0:      set_episode 00000000
        set_floor_handler 00000000, 100
        set_qt_success 250
300:    sync_register R255, 00000001
250:    window_msg 'Thank you for completing the job.<cr>Please take your reward.'
        winend 
        ret 
```

Remarks:  
+ Variables must be defined before the main code or the parser will fail.

#### Include Files
With the directive `%include`, PASM source code from another file can be inserted into the current source file during transcompilation.

Syntax:
```
%include "filepath"
```
where `filepath` is the path to the PASM file to include. The path must be relative to the current file.

Example:
```
[ File wait.pasm ]
200:    sync 
        subi R70, 1
        jmpi_> R70, 0, 200
        ret 
		
[ File main.pasm ]
%include "./utils/wait.pasm"

0:      set_episode 0
        BB_Map_Designate 00, 00, 00, 00
		jmp 300
		ret
300:    seti R70, 30 // Waits for 1s
        call 200
		ret
		
[ Result file qe_main.pasm ]
200:    sync 
        subi R70, 00000001
        jmpi_> R70, 00000000, 200
        ret 
0:      set_episode 00000000
        BB_Map_Designate 00, 0000, 00, 00
        jmp 300
        ret 
300:    leti R70, 0000001E
        call 200
        ret 

```

Remarks:  
+ Filename must be quoted.
+ Includes must be defined before the main code or the parser will fail.

#### Macros
A macro is a sequence of OP codes referenced by a name that could be used anywhere in the code.  
When a sequence of instructions is used many times, they can be put in a macro and use it instead of writing the instructions all the time.

Syntax:
```
%macro  macroname(*args)
		[ OP code 1 ]
		[ OP code 2 ]
		...
```
where `macroname` must be a valid [identifier name](#identifier-name),  
`args` is a comma-separated list of arguments (like variables but they don't use the `$` prefix).

To invoke a macro, use the macro name along with a number of parameters.  
Syntax:
```
macroname(*args)
```

Example:
```
%macro  wait(frames)
		leti R70, frames
		call 200
		
300:    wait(30) // Wait 1s
        ret 
		
[ Result ]
300:    leti R70, 0000001E
        call 200
        ret 
```

## Appendix
### Identifier name
An identifier is a word that contain the character `_` and/or any of the following character ranges: `a-z`, `A-Z`, `0-9`.