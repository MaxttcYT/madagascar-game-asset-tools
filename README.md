# Madagascar Tools

## MADAGASCAR BSP PARSER

1. Put all BSPS from a level into `bsps/`
2. Put all TEXTURES from a level into `parsed_bsps/textures/` in PNG format
3. Run `parse_bsps.py`
4. You can now import all into blender or something other but exclude the obj with `_COL` in its name, its for collision and hidden in game
5. It should correctly show geometry but textures witll be messed up

## Stream unpack / repack

### Unpack

arg1: stream input

arg2: out folder

`python3 stream_unpack.py banquet.stream banquet`

### Repack

arg1: unpackaged files folder path

arg2: output stream file path

`python3 stream_unpack.py banquet banquet_new.stream`

then copy the new .stream into your game folder and rename it to the level you unpacked originally BUT MAKE BACKUP OF ORIGINAL FIRST!!!!!!!!

### OTHER INFO

the included `banquet_repack.stream` may only function on PC GERMAN because i unpackaged from there, it adds a cube to the totems, the `banquet.stream` is also the untouched german version for PC
