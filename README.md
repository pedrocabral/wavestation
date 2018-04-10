# wavestation

wstation is a Python module to read [Korg Wavestation](https://en.wikipedia.org/wiki/Korg_Wavestation) preset bank files in .syx (SysEx) and .wsram (vst plugin/Korg Legacy) formats and parse the data into an object oriented tree, representing the hierarchical architecture of the synthesizer's preset data structures. Using some of the built-in methods, it makes possible to easily edit names, configurations and effects and save or export the original/edited preset banks in other formats (hardware/vst plugin).

I started this project with no objective other than to understand the synthesizer system exclusive implementation and the internal   data structures while reading the Korg published [Wavestation Developer Information](http://www.danphillips.com/wavestation/ws_developer.htm) docs and trying to figure out if it would be possible to convert .wsram files (from the vst plugin) to .sys files (system exclusive - SysEx) to be loaded into the keyboard/rackmount model (hardware). After getting some results, I decided to share as it might be useful for someone else.

It was tested on Python 3.5.2 and on 2.7.12, both working as expected

----
### Basic usage

**Loading a System Exclusive file (.syx) bank.** (same process to load .wsram)
```python
>>> import wstation

>>> io = wstation.WSIO()
>>> filepath = 'system_file_path/sysex_bank_file.syx'
>>> bank = io.load_bank(filepath)
>>> bank

<WSBank>

>>> print(bank)
'''
Wavestation Bank
----------------
Performances: 100
Patches: 70
Wave Sequences: 32
Wave Steps: 379
'''
>>> bank.perfs[0].name  # acessing the first performance name

'Ski Jam'

>>> bank.perfs[0].parts[0].parameters  # acessing the 1st performance (1st part) parameters dict

{'bank_num': 0, 'hi_key': 60, 'tunetab': 0, 'lo_vel': 1, 'part_mode': 52, 'midi_out_chan': 0, 
'midi_prog_num': 0, 'micro_tune_key': 0, 'key_priority': 0, 'sus_enable': 0, 'lo_key': 7, 
'bank_expansion': 0, 'level': 80, 'patch_num': 0, 'delay': 0, 'detune': 0, 'voice_mode': 1, 
'hi_vel': 127, 'play_mode': 3, 'output': 104, 'trans': 0}
```
The io object is a WSIO class instance from wstation module and holds all methods and parameters to read and export preset data. when calling the load_bank() method, it returns a Bank class instance containing all bank preset data formatted in a tree. [read more about it below](#bank). The bank instance can be used to inspect and edit data.
 The WSIO object can also export the bank tree to other formats. 

**Exporting a bank to sysex or wsram file format**
```python
# sysex file export (.syx)

>>> export_filepath = 'system_file_path/sysex_bank_file.syx'
>>> io.export_sysex(bank, export_filepath)

# wsram file export (.wsram)

>>> export_filepath = 'system_file_path/wsram_bank_file.wsram'
>>> io.export_wsram(bank, export_filepath)
```

#### More usage examples

In the [wavestation\tests](https://github.com/pedrocabral/wavestation/tests) folder you will find along some unit tests and public preset bank samples, a file named usage.py, when executed, it loads a preset and run a series of demonstration functions, accessing every structural element of the bank and printing the results. Calls to the functions are at the end of the file and can be commented if it is the case to generate a lesser verbose output, for better reading.

### <a name="bank"></a>Bank Data Structure
The WSBank instance object holds all preset bank data as properties forming a data tree that represents the synth own internal preset structures. Every built object instance in the tree, except for WSBank (root) and Perf classes, contains a 'parameters' property, which holds a dictionary containing the actual loaded data for that specific synth block structure segment. It maps the keys as parameter names and the values as integers, most of the time containing direct values, but sometimes containing an index to a specific table of values.
Any parameters dictionary can be directly accessed to perform value changing. A very basic parameter limitation was implemented, raising an exception if the changed value exceeds the expected size for that specific parameter. The WSBank class  also contains a few helper methods, returning text (string) describing parameter names (keys) and expected values (limits) for each parameter.

**Scheme of the bank object tree properties:**
```
WS Bank Structure               object adressing

<WSBank>                        bank
    |
    .perfs <Perf> list          bank.perfs[0]
        |.fx <Fx> list          bank.perfs[0].fx[1]
        |.parts <Part> list     bank.perfs[0].parts[0]
    .patches <Patch> list       bank.patches[0]
        |.osc <OSC> list        bank.patches[0].osc[0]
    .wseqs <Wseq> list          bank.wseqs[0]
        |.steps <Step> list     bank.wseqs[0].step[0]

# Objects Properties

<WSBank> - Wavestation Bank - object Properties (Root)   bank
| .perfs - Performances - list of <Perf> objects         bank.perfs
| .patches - Patches - list of <Patch> objects           bank.patches
| .wseqs - Wave Sequences - list of <Wseq> objects       bank.wseqs

<Perf> properties:
| .fx - list of 3 (fixed) <Fx> obj. [rout., Fx1, Fx2]    bank.perfs[0].fx
| .parts - list of 8 <Part> objects                      bank.perfs[0].parts
|
|   <Fx> property:
|   | .parameters - dict {par name (str): value (int)}   bank.perfs[0].fx.parameters
|   <Part> properties:
|   | .parameters - dict {par name (str): value (int)}   bank.perfs[0].part[0].parameters

<Patch> properties:
| .parameters - dict - par name (str): value (int)       bank.patches[0].parameters
| .osc - Oscilators - list of <OSC> objects              bank.patches[0].osc
|
|   <OSC> property:
|   | .parameters - dict {par name (str): value (int)}   bank.patches[0].osc[0].parameters

<Wseq> properties
| .parameters - dict {par name (str): value (int)}       bank.wseqs[0].parameters
| .steps - list of <Step> objects                        bank.wseqs[0].steps
|
|    <Step> Property
|   | .parameters - dict of parameters {name: value}     bank.wseqs[0].steps[0].parameters
```
### Effects
Performances instances \<Perf\> (in fx property) contains a list with a fixed number of 3 Fx object instances. The first holds the routing configuration and the others, one effect data each. Changing (editing) the pre-defined effect parameters can be done directly by acceessing the Fx 'parameters' property dictionary, as explained above. (see [bank structure](#bank))

To change the effect object itself (Fx instance in fx list) to one of the (up to) 55 available built-in effects, as each different effect has its own specific parameters, default settings, and limits, it is necessary to use an FxBuilder (class) instance to "build" a new Fx instance object. It also contains the change_fx() method that allows to easily change effect objects from the <Perf> fx list by entering the list and the desired effect number for the fx location. There are also in this class, help methods that list effects, parameters, and limits for each effect parameter.

The effects are divided into groups (delays, reverbs, choruses...) and each group share the same parameters.

**Changing Effect number 1 from "Quadrature Chorus" to "Enhancer - Exciter"**

```python
>>> fxb = wstation.FxBuilder()
>>> perf_fx = bank.perfs[0].fx  # performance 0 fx list
>>> print(perf_fx)

[<Fx -1: Series Routing>, <Fx 22: Quadrature Chorus - EQ>, <Fx 10: Early Reflections - EQ 1>]
 
>>> fxb.change_fx(perf_fx, fx1_number=28) # routing=None, fx2_number=None (defaults to None - keeps fx) 
>>> print(perf_fx)

[<Fx -1: Series Routing>, <Fx 28: Enhancer - Exciter - EQ>, <Fx 10: Early Reflections - EQ 1>]
```

### Important aspects to consider about SysEx transfers
It is important to be aware that there are many differences between all produced WS synth versions. Each newer model released accumulated new features, including RAM and ROM banks and sometimes effects. For this reason, some backwards compatibility issues may occur in preset data exchange between different versions. When the synth receives a preset which brings some reference to a PCM wave added to a newer version (not present in the synth) it points the reference to a different wave other than the intended one. If this happens, it is recommended to edit the preset and change the reference from the missing wave to the most similar wave present in the synth, and try to achieve a similar sounding preset.

 Those issues are independent of this module usage because it only deals with the references to sounds and not the actual PCM sound data (fixed in the synth's memory banks). It is recommended, when exporting presets, to always consider the model versions (exporting and receiving data) in order to avoid those issues. By being careful to use the same PCMs and effects present in the synth which will receive the data, it is possible to have the exact same sounding preset exported from a newer ws version (even the vst plugin), via sysex file export.

Although it is very improbable that loading imported data converted using this module causes any kind of damage, I have to state that the use of this module is at the user’s sole risk.
