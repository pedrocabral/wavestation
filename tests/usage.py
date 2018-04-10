#!/usr/bin/env python

import os
import wstation


def comment(text):
    st = '{0}{0}{1}{0}{2}{0}{1}{0}{0}'.format('\n', '-' * 80, text)
    return st


def print_bank_structure():
    """
    WS Bank Structure

    <WSBank>                        bank
        |
        .perfs <Perf> list          bank.perfs[0]
            |.fx <Fx> list          bank.perfs[0].fx[1]
            |.parts <Part> list     bank.perfs[0].parts[0]
        .patches <Patch> list       bank.patches[0]
            |.osc <OSC> list        bank.patches[0].osc[0]
        .wseqs <Wseq> list          bank.wseqs[0]
            |.steps <Step> list     bank.wseqs[0].step[0]

    Objects Properties

    <WSBank> - Wavestation Bank - object Properties (Root)        bank
    | .perfs - Performances - list of <Perf> objects              bank.perfs
    | .patches - Patches - list of <Patch> objects                bank.patches
    | .wseqs - Wave Sequences - list of <Wseq> objects            bank.wseqs

    <Perf> properties:
    | .fx - list of 3 (fixed) <Fx> objects [routing, Fx1, Fx2]    bank.perfs[0].fx
    | .parts - list of 8 <Part> objects                           bank.perfs[0].parts
    |
    |   <Fx> property:
    |   | .parameters - dict {par name (str): value (int)}        bank.perfs[0].fx.parameters
    |   <Part> properties:
    |   | .parameters - dict {par name (str): value (int)}        bank.perfs[0].part[0].parameters

    <Patch> properties:
    | .parameters - dict - par name (str): value (int)            bank.patches[0].parameters
    | .osc - Oscilators - list of <OSC> objects                   bank.patches[0].osc
    |
    |   <OSC> property:
    |   | .parameters - dict {par name (str): value (int)}        bank.patches[0].osc[0].parameters

    <Wseq> properties
    | .parameters - dict {par name (str): value (int)}            bank.wseqs[0].parameters
    | .steps - list of <Step> objects                             bank.wseqs[0].steps
    |
    |    <Step> Property
    |   | .parameters - dict of parameters {name: value}          bank.wseqs[0].steps[0].parameters

    """
    print(print_bank_structure.__doc__)


# loading files


def load_banks(sysex, wsram):

    wsio = wstation.WSIO()
    bank1 = wsio.load_bank(sysex)
    bank2 = wsio.load_bank(wsram)

    return wsio, bank1, bank2


# listing Structures


def print_perfs(bank):
    print(comment('Bank Performances - Python list of Perf objects'))
    # repr a python list with performances
    print(bank.perfs)
    print(comment('Bank Performances - Listing'))
    # print a list of all performances names in the bank
    print('\n'.join(['{} {}'.format(p.number, p.name) for p in bank.perfs]))


def print_patches(bank):
    print(comment('Bank Patches - Python list of Patch objects'))
    # repr a python list with patches
    print(bank.patches)
    print(comment('Bank Patches - Listing'))
    # print a list of all patches names in the bank
    print('\n'.join(['{} {}'.format(p.number, p.name) for p in bank.patches]))
    print(comment('Bank Patch 0 (1st) - Parameters'))
    # print one patch parameters
    print(bank.patches[0])


def print_wseqs(bank):
    print(comment('Bank Wave Sequences (32 per bank) - Python list of WaveSeq objects'))
    # repr a python list with wave sequences
    print(bank.wseqs)
    print(comment('Bank Wave Sequences - Listing'))
    # print a list of all patches names in the bank
    print('\n'.join(['{} {}'.format(p.number, p.name) for p in bank.wseqs]))
    print(comment('Bank Wave Sequence 2 - Parameters'))
    # print one wseq parameters
    print(bank.wseqs[2])


def print_parts(bank):
    print(comment('Bank Performances Parts (8 per Perf) - Python list of Part objects'))
    # repr python parts list from perf number 0
    print(bank.perfs[0].parts)
    print(comment('Part number 0 (1st) from Bank Performance number 0 (1st) - Parameters'))
    # print from the first performance, the parameters from the first part
    print(bank.perfs[0].parts[0])


def print_oscilators(bank):
    print(comment('Bank Patches Oscilators (up to 4 per patch) - Python list of OSC objects'))
    # repr list of oscs from patch 0
    print(bank.patches[0].osc)
    print(comment('OSC 1 From Bank Patch 0 - Parameters'))
    # print one osc parameters
    print(bank.patches[0].osc[1])


def print_steps(bank):
    print(comment('Bank Steps from Wave Sequences (variable qtty) - Python list of Step objects'))
    # repr python steps wseqs list from 1 wave sequence
    print(bank.wseqs[0].steps)
    print(comment('Bank Step 0 from Bank Wave Serquence 0 - Parameters'))
    # repr parameters for one step
    print(bank.wseqs[0].steps[0])


# help


def help_ws(bank):
    print(comment('List all parameters for each wavestation structure'))
    # list all parameters - except performances (no parameters) and Effects
    print(bank.help_all_params())
    print(comment('List parameters and values for one object'))
    # list parameters and values for one object - except performances (no parameters) and Effects
    print(bank.help_parameters(bank.patches[1]))
    print(comment('List obj parameter and value for a specific parameter'))
    # list only the parameter and value for a specific parameter index
    print(bank.help_param_by_index(bank.wseqs[0], 4))
    print(comment('List Effects parameters, valuesand ranges, by performance number (index) and fx number (index)'))
    # list fx parameters by performance number (index) and fx number ([0, 1, 2] - routing, fx1, fx2)
    print(bank.help_fx_params_by_number(0, 1))


# fx


def fx_help(bank):
    fxb = wstation.FxBuilder()
    print(comment('List all effects and related groups - Effects Listing'))
    # list all effects and related groups
    print(fxb.help_all_fx_listing())
    print(comment('List effect parameters by effects group - all effects in the group share the same parameters'))
    # print effects parameters by group
    print(fxb.help_fx_params_by_group(1))
    print(comment('List effect parameters by fx object - includes parameters'))
    # list fx parameters by fx object - includes fx parameters
    print(fxb.help_fx_params(bank.perfs[0].fx[2]))
    print(comment('List effect parameters by perf number (index) and fx position index'))
    # list fx parameters by perf number (index) and fx position index ([0, 1, 2] -> [routing, fx1, fx2])
    # it is not necessary to construct the FxBuilder object as it is a WSBank method
    print(bank.help_fx_params_by_number(0, 1))


def fx_edit(bank):
    print(comment('Effect Parameters Edition - Printing Current Parameters'))
    # print effect number, name and parameters
    fx = bank.perfs[0].fx[1]
    print(fx)
    print()
    # print effect parameters dictionary
    print(fx.parameters)
    print()
    print(comment('Effect Parameters Edition - Change \'delay time right\' (not indexed) value'))
    # print parameter (4) range (not indexed parameter)
    print(bank.help_fx_params(fx, parnumber=4))
    # change parameter to 60
    fx.parameters['delay time right'] = 60
    print(bank.help_fx_params(fx, parnumber=4))
    print(comment('Effect Parameters Edition - Change delay value for a value out of range'))
    # change parameter to some value out of range
    try:
        fx.parameters['delay time right'] = 512
    except Exception as e:
        print('Exception ', str(e), '\n')

    print(comment('Effect Parameters Edition - Change \'footswitch enable\' (indexed) value'))
    # print parameter (1) range (indexed parameter)
    print(bank.help_fx_params(fx, parnumber=1))
    # change parameter to 'enable'
    fx.parameters['footswitch enable'] = 1
    print(bank.help_fx_params(fx, parnumber=1))
    print(comment('Effect Parameters Edition - Change indexed value for a value out of range'))
    # change parameter to some value out of range
    try:
        fx.parameters['footswitch enable'] = 5
    except Exception as e:
        print('Exception ', str(e), '\n')


def fx_change(bank):
    print(comment('Changing Performance Effects - Python list of Fx objects'))
    print(bank.perfs[0].fx)
    print(comment('Effect name and parameters - Effect index 1 [0, 1, 2] -> [routing, fx1, fx2]'))
    print(bank.perfs[0].fx[1])
    c = 'Changing Effect index 1 in a loop for all available effects and printing name'
    c += '\nand default parameters. Observe the effect changing in the fx list - index 1'
    print(comment(c))
    fxb = wstation.FxBuilder()
    for i in range(56):
        # change fx1 to all available effects and print new fx default parameters
        fxb.change_fx(bank.perfs[0].fx, fx1_number=i)
        print('')
        print(bank.perfs[0].fx)
        print('')
        print(bank.perfs[0].fx[1])
    print()


# Exports


def export_bank_2_formats(wsio, bank, expsyx, expwsr):
    print(comment('Export 2 different formats (sysex and swram using the same bank'))
    # export system exclusive sysex (hardware)
    wsio.export_sysex(bank, expwsr)
    # export wsram (vst plugin)
    wsio.export_wsram(bank, expsyx)


if __name__ == "__main__":

    location = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    filepath = os.path.join(location, ) + '\\'

    sysex_file = filepath + "factory.syx"
    wsram_file = filepath + "factory.wsram"
    exp_sysex = filepath + "export.syx"
    exp_wsram = filepath + "export.wsram"

    io, bnk1, bnk2 = load_banks(sysex_file, wsram_file)
    print_bank_structure()
    print_perfs(bnk1)
    print_patches(bnk1)
    print_wseqs(bnk1)
    print_parts(bnk1)
    print_oscilators(bnk1)
    print_steps(bnk1)
    help_ws(bnk1)
    fx_help(bnk1)
    fx_edit(bnk1)
    fx_change(bnk1)
    # Exporting and saving 2 different bank formats
    # export_bank_2_formats(io, bnk1, exp_sysex, exp_wsram)
