# PSO ASM syntax highlighting for Notepad++
Provides syntax highlight and automatic completion for [Phantasy Star Online](https://en.wikipedia.org/wiki/Phantasy_Star_Online) [quest scripts](https://qedit.info) (PSO ASM, or PASM), using [Notepad++](https://notepad-plus-plus.org/)'s [User Defined Language](http://udl20.weebly.com/).

## Installation
1. Download UDL file [PSO_asm.xml](https://raw.githubusercontent.com/raohmaru/psoasm-npp-udl/master/udl/PSO_asm.xml).
2. Open Notepad++.
3. Go to "Language > Define your language...".
4. Click on "Import..." button, browse to the location where `PSO_asm.xml` was saved and open it.
5. Restart Notepad++.

### Auto-completion File
1. Close Notepad++.
2. Download API file [PSO_asm.xml](https://raw.githubusercontent.com/raohmaru/psoasm-npp-udl/master/api/PSO_asm.xml).
3. Move the downloaded file to the "plugins\APIs\" subfolder of your Notepad++ installation folder.
4. Open a .pasm file with Notepad++ and check if auto-completion is working by typing the name of a [OP code](https://qedit.info/index.php?title=OPCodes).

## How to use
Open a .pasm file and enable the syntax highlight by selecting "Language > PSO asm".

## Theme Colors
The colors of the syntax highlighting for PSO asm works better with the theme Monokai. If you want to change the colors to fit your theme, you can use the [Used Define Language](http://docs.notepad-plus-plus.org/index.php/User_Defined_Languages) tool in Notepad++, or edit the `PSO_asm.xml` file and import it again as explained in Installation.

## Parsing and Syntax Checking
PASM files cannot be directly imported into [QEdit](https://qedit.info/index.php?title=Main_Page) unless the format is correct (and QEdit is very picky with it). To ensure compatibility, there is a [parser and checker utility](https://github.com/raohmaru/psoasm-npp-udl/tree/master/parser) written in Python in the parser/ folder that will create a formatted file to be imported in QEdit.

## Credits
The PSO ASM syntax highlighting file and the parser were originally developed by Thomas Neubert and released in Ephinea's forum site:  
https://www.pioneer2.net/community/threads/writing-pasm-quest-scripts-in-a-text-editor.9828/

## License
Released under The MIT License (MIT).
