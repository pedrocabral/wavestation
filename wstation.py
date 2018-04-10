#!/usr/bin/env python

import os
import json
import struct
import weakref
import binascii
from copy import deepcopy


_def = os.path.join(os.path.dirname(__file__), 'definition.json')


class Base(object):
    def _load_par(self, filestr):
        with open(filestr) as jsonfile:
            dic = json.load(jsonfile)
            blocks = dic['blocks']
            dic['blocks'] = dict(zip(blocks.keys(), [self._h2b(v) for v in blocks.values()]))
            return dic

    @staticmethod
    def _byte(bt):
        if isinstance(bt, str) and len(bt) == 1:
            bt = ord(bt)
        st = struct.Struct('B')
        return st.pack(bt)

    @staticmethod
    def _ord(bt):
        if isinstance(bt, int):
            return bt
        elif isinstance(bt, str) and len(bt) == 1:
            return ord(bt)
        else:
            return ord(bt.decode())

    @staticmethod
    def _sign_int(binarystr):
        """Convert 2 complementary binary string (of any bit size) to a signed int"""
        mask = 1 << (len(binarystr) - 1)
        value = (int(binarystr, 2) ^ mask) - mask
        return value

    @staticmethod
    def _signed_binstr(sint, size):
        """Convert a signed int to a 2 complementary binary string"""
        fsize = size
        if sint > 0:
            chk = len(format(abs(sint), 'b')) > size - 1
        else:
            chk = len(format(abs(sint + 1), 'b')) > size - 1
        if sint > 0:
            size -= 1  # 7 bits available
        if chk:
            raise (Exception('value ({}) over limits for the size ({} bits signed)'.format(sint, fsize)))

        value = format(sint & int('1' * size, 2), '0{}b'.format(fsize))

        return value

    @staticmethod
    def _b2h(binary, *args):
        return binascii.hexlify(binary)

    @staticmethod
    def _h2b(string, *args):
        return binascii.unhexlify(string)

    @staticmethod
    def _pack(data, structstr):
        if isinstance(data, list) or isinstance(data, tuple):
            return struct.Struct(structstr).pack(*data)
        else:
            return struct.Struct(structstr).pack(data)

    @staticmethod
    def _unpack(binary, structstr):
        return struct.Struct(structstr).unpack(binary)

    @staticmethod
    def _denibble(byte_0, byte_1):
        b0 = ord(byte_0)
        b1 = ord(byte_1) << 4
        st = struct.Struct('B')
        return st.pack(b0 | b1)

    @staticmethod
    def _nibbler(byte):
        b0 = ord(byte)
        b1 = b0 >> 4
        b2 = b0 & 15
        st = struct.Struct('B')
        return st.pack(b2), st.pack(b1)


class WSIO(Base):
    def __init__(self):
        par = self._load_par(_def)
        self._strc = par['struct']
        self._blks = par['blocks']
        self._lims = par['limits']
        self._parm = par['params']
        self.type = None  # defined @property
        self._file = None  # defined @property
        self._fxbuilder = FxBuilder()

    @property
    def file(self): return self._file

    @file.setter
    def file(self, f):
        self.type = self._check_file_type(f)
        self._file = f

    def _check_file_type(self, fl):

        with open(fl, "rb") as f:
            first_bytes = f.read(3)
            if first_bytes == self._blks['sysex']:
                return 0
            elif first_bytes == self._blks['wsram']:
                return 1
            else:
                raise (Exception("Unknown file type"))

    def _sysex_mapper(self, sysex):
        byte = '0'
        st = self._blks['st']
        en = self._blks['en']
        header, locate, chksum = [], [], []
        # cnt = 0
        s = 0
        with open(sysex, 'rb') as sf:
            while byte:
                byte = sf.read(1)
                cnt = int(sf.tell())
                if byte == st:
                    header.append(byte + sf.read(5))
                    cnt = int(sf.tell())
                    s = cnt
                if byte == en:
                    loc = (s, cnt - 2)
                    locate.append(loc)
                    sf.seek(loc[1], 0)
                    ck = sf.read(1)
                    chksum.append(ord(ck))
                    sf.seek(cnt, 0)
            return header, locate, chksum

    def _load_sysex(self, filepath):
        headers, positions, checksums = self._sysex_mapper(filepath)
        maps = [i for i in zip(headers, positions, checksums)]
        ready = [False, False, False]
        korg = self._blks['korg']
        wvst = self._blks['wvst']
        perf = self._blks['perf']
        patc = self._blks['patc']
        wavs = self._blks['wavs']

        headers, positions, checksums, types = [], [], [], []

        for m in maps:

            kook = m[0][1:2] == korg
            wsok = m[0][3:4] == wvst
            oook = kook and wsok

            peok = oook and m[0][4:5] == perf
            paok = oook and m[0][4:5] == patc
            waok = oook and m[0][4:5] == wavs

            ok = ((peok, self._blks['perf']), (paok, self._blks['patc']), (waok, self._blks['wavs']))

            for c, t in enumerate(ok):
                if t[0]:
                    types.append(t[1])
                    headers.append(m[0])
                    positions.append(m[1])
                    checksums.append(m[2])
                    ready[c] = True

        if not all(ready):
            raise (Exception('sysex file is not from korg, wavestation or it is incomplete'))

        data = []
        with open(filepath, 'rb') as f:
            for c, p in enumerate(positions):
                buf = b''
                ck = 0
                f.seek(p[0], 0)
                for i in range(int((p[1] - p[0]) / 2)):
                    b0, b1 = f.read(1), f.read(1)
                    ck += ord(b0) + ord(b1)
                    byte = self._denibble(b0, b1)
                    buf += byte

                data.append(buf)

                if ck % 128 != checksums[c]:
                    raise (Exception('Checksum fails, sysex file may be corrupt'))

        bank = WSBank(self._parm)

        for c, t in enumerate(types):
            if t == self._blks['perf']:
                self._load_perfs(data[c], bank)

        for c, t in enumerate(types):
            if t == self._blks['patc']:
                self._load_patches(data[c], bank)

        for c, t in enumerate(types):
            if t == self._blks['wavs']:
                self._load_waveseqs(data[c], bank, 8528)  # names offset

                buf = data[c][528:]
                stepmap = [(ws.parameters['ws_link'], ws.parameters['ws_loop_end'] + 1) for ws in bank.wseqs]
                cnt = self._cnt()

                for ct, cut in enumerate(stepmap):
                    self._load_steps(buf, bank, ct, cut[1], cnt)

        return bank

    def _load_perfs(self, buf, bank):
        cnt = self._cnt()  # byte counter
        perf, fx = (16, 'name', self._unpack_str, 'str16', 0), (21, 'fx', self._unpack_fx, None, 0)
        part = (18, '_rawparam', self._unpack_part, None, 0)
        idx = [(50, Perf, 'perfs', (perf, fx, [(8, Part, 'parts', (part,))]))]  # comma to keep single content tuple
        self._load_data(bank, buf, idx, (cnt,))

    def _load_patches(self, buf, bank):
        cnt = self._cnt()
        patch = (16, 'name', self._unpack_str, 'str16', 0)
        param = (74, '_rawparam', self._unpack, self._strc['patch'], 0)
        osc = (84, '_rawparam', self._unpack_osc, None, 0)
        idx = [(35, Patch, 'patches', (patch, param, [(4, OSC, 'osc', (osc,))]))]
        self._load_data(bank, buf, idx, (cnt,))

    def _load_waveseqs(self, buf, bank, names_addr):
        cnt = self._cnt()
        cnt1 = self._cnt(names_addr)
        wseq = (16, '_rawparam', self._unpack_wseq, None, 0)
        name = (8, 'name', self._unpack_str, 'str8', 1)
        idx = [(32, WaveSeq, 'wseqs', (wseq, name))]
        self._load_data(bank, buf, idx, (cnt, cnt1))

    def _load_steps(self, buf, bank, count, steps, cnt):
        step = (16, '_rawparam', self._unpack, self._strc['wstep'], 0)
        idx = [(steps, Step, 'steps', (step,))]
        self._load_data(bank.wseqs[count], buf, idx, (cnt,))

    def _load_wsram(self, filepath):
        bank = WSBank(self._parm)
        data = []
        pad = self._blks['fill']

        with open(filepath, 'rb') as f:
            f.seek(16, 0)
            data.append(f.read(9050))  # perfs
            data.append(f.read(14910))  # patches
            wseq = f.read(512)  # wseqs 512
            steps = [b''.join(filter(lambda x: x != pad, [f.read(16) for _ in range(256)])) for _ in range(32)]  # steps
            wseq += f.read(256)  # wseqs names
            data.append(wseq)
            data.append(steps)

        self._load_perfs(data[0], bank)
        self._load_patches(data[1], bank)
        self._load_waveseqs(data[2], bank, 512)

        for c, rawsteps in enumerate(data[3]):
            cnt = self._cnt()
            step_num = len(rawsteps) // 16
            self._load_steps(rawsteps, bank, c, step_num, cnt)

        return bank

    @staticmethod
    def _cnt(start=0):
        accum = start
        while True:
            value = yield
            accum += value
            yield accum

    def _load_data(self, obj, buf, idx, counters):
        """
        loads and formats data
        Keyword arguments:
            obj -- node instance - receives built ws objects in its attributes - Bank instance (start/root)
            buf -- binary buffer
            idx -- list containing parameters to build and process data
            idx -- [(rep, new_obj, where, ((param), (param) , [(rep, new_obj, where, ((param), ...))])] (list)
                   rep -- repetitions (int),
                   new_obj -- new instance to be created and filled with data (class),
                   where -- property in main obj to receive the new objects (str)
                   param -- (n, name, filter, filter parameters)
                            n -- bytes to read (int)
                            name -- property in new instance to receive the data (str)
                            filter -- function to process data (method), None if not needed
                            parameters -- extra parameter to the filter, None if not needed
            counters -- tuple containing one or more counter (generators) instances that
                        stores the sum and keeps counting in recursion
        Returns:  None
        """
        for i in idx:
            for ct in range(i[0]):
                o = i[1](self._parm[i[1].__name__][0])
                o._limits = (self._lims['sizes'][o.__class__.__name__], self._lims['limits'])
                o.number = ct
                for p in i[3]:
                    if isinstance(p, tuple):
                        cnt = counters[p[4]]
                        next(cnt)
                        c = cnt.send(0)
                        next(cnt)
                        c0, c1 = c, cnt.send(p[0])
                        binary = buf[c0:c1]
                        process = p[2](binary, p[3])
                        setattr(o, p[1], process)
                    elif isinstance(p, list):
                        self._load_data(o, buf, p, counters)
                att = getattr(obj, i[2])
                att.append(o)

    def _unpack_str(self, binary, unp_str):
        """unpacks chars"""
        name = self._unpack(binary, self._strc[unp_str])[0]
        n = bytearray([i if 32 < i < 127 else 32 for i in bytearray(name)])
        return n.decode()

    def _unpack_part(self, binary, *args):
        """unpacks part parameters and extract extra params"""
        main_par = list(self._unpack(binary, self._strc['part']))
        part_mode = '{:08b}'.format(main_par[4])
        extra_par = [int(part_mode[i:i + 2], 2) for i in range(len(part_mode)) if i % 2 == 0]
        return tuple(main_par + extra_par)

    def _unpack_osc(self, binary, *args):
        """unpacks osc parameters and extract extra params"""
        main_par = list(self._unpack(binary, self._strc['osc']))
        lfo1sh, lfo2sh = '{:08b}'.format(main_par[9]), '{:08b}'.format(main_par[18])
        lfo1syn, lfo2syn = int(lfo1sh[0]), int(lfo2sh[0])
        lfo1sh, lfo2sh = int('{:0>8s}'.format(lfo1sh[1:]), 2), int('{:0>8s}'.format(lfo2sh[1:]), 2)
        out = main_par[0:9] + [lfo1sh, lfo1syn] + main_par[10:18] + [lfo2sh, lfo2syn] + main_par[19:]
        return tuple(out)

    def _unpack_wseq(self, binary, *args):
        """unpacks wseq parameters and extract extra params"""
        main_par = list(self._unpack(binary, self._strc['wseq']))
        loop_count = '{:08b}'.format(main_par[4])
        loop_dir = int(loop_count[0])
        loop_count = int(loop_count[1:], 2)
        out = main_par[0:4] + [loop_count, loop_dir] + main_par[5:]
        return tuple(out)

    @staticmethod
    def _bytecnt(c=0):
        while True:
            yield c & 255
            c += 1

    def _unpack_fx(self, binary, *args):
        """unpacks binary and returns fx object with all related parameters"""
        return self._fxbuilder._unpackfx(binary)

    def _pack_fx(self, fxlist, *args):
        """reads fx object and packs 21 bytes to build file"""
        return self._fxbuilder._packfx(fxlist)

    def _file_build(self, bank):  # expfn
        """"""
        prnam, prfx = ('name', self._pack_str, 'str16'), ('fx', self._pack_fx, None)
        part = [('parts', (('_rawparam', self._pack_part, None),))]

        ptnam, ppar = ('name', self._pack_str, 'str16'), ('_rawparam', self._pack, self._strc['patch'])
        posc = [('osc', (('_rawparam', self._pack_osc, None),))]

        wsnam, wspar = ('name', self._pack_str, 'str8'), ('_rawparam', self._pack_wseq, None)
        stp = [('steps', (('_rawparam', self._pack, self._strc['wstep']),))]

        idx = [('perfs', (prnam, prfx, part)), ('patches', (ptnam, ppar, posc)),
               ('wseqs', (wspar,)), ('wseqs', (stp,)), ('wseqs', (wsnam,))]

        return self._read_bank(bank, idx)

    @staticmethod
    def _file_export(filename, data):
        with open(filename, 'wb') as f:
            f.write(data)

    def _read_bank(self, bank, idx):
        data = []
        for i in idx:
            buf = b''
            for el in getattr(bank, i[0]):
                for p in i[1]:
                    if isinstance(p, tuple):
                        buf += p[1](getattr(el, p[0]), p[2])
                    elif isinstance(p, list):
                        buf += b''.join(self._read_bank(el, p))
            data.append(buf)
        return data

    def load_bank(self, filepath):
        """Interface to Call proper "load method" according to bank file type (sysex / wsram)"""
        self.file = filepath
        if self.type == 0:  # sysex
            return self._load_sysex(self.file)
        elif self.type == 1:  # wsram
            return self._load_wsram(self.file)
        else:
            raise Exception('Unknown File type')

    def export_sysex(self, bank, filepath):
        """export sysex file"""
        bkcp = deepcopy(bank)
        cnt = 1
        stepcnt = 0
        bcnt = self._bytecnt()
        prevcnt = 1
        link = (1, 1)
        for wseq in bkcp.wseqs:
            scnt = self._bytecnt()
            nst = len(wseq.steps)
            if nst <= 1:
                link = (0, 0)
            wseq.parameters['ws_link'], wseq.parameters['ws_slink'] = link
            stepcnt += nst
            cnt += nst
            link = (cnt, cnt)
            for step in wseq.steps:
                sc = next(scnt)
                c = next(bcnt)
                if sc == 0:
                    vals = (0, c + 2)
                elif sc == nst - 1:
                    vals = (c, 0)
                    step.parameters['ws_llink'] = prevcnt
                else:
                    vals = (c, c + 2)
                step.parameters['ws_blink'], step.parameters['ws_flink'] = vals
            prevcnt = cnt

        fill = Step(self._parm['Step'])
        fill._limits = (self._lims['sizes']['Step'], self._lims['limits'])
        fill._rawpar = (int('ffff', 16), 0, 0, 0, 0, 0, 0, 0, 0, 0)

        bkcp.wseqs[0].steps = [fill] + bkcp.wseqs[0].steps
        bkcp.wseqs[31].steps = bkcp.wseqs[31].steps + ([fill] * (500 - stepcnt))

        perf, patch, wseq, steps, wsnam = self._file_build(bkcp)
        process = [perf, patch, wseq + steps + wsnam]

        chk = [0, 0, 0]
        for c, p in enumerate(process):
            p = b''.join([b''.join(self._nibbler(self._byte(i))) for i in p])
            for b in p:
                chk[c] += self._ord(b)
            process[c] = p

        chk = [self._byte(c % 128) for c in chk]
        perf, patch, waves = process
        pf, pa = self._blks['perfs'], self._blks['patches']
        wq, en = self._blks['waves'], self._blks['end']
        buf = pf + perf + chk[0] + en + pa + patch + chk[1] + en + wq + waves + chk[2] + en
        self._file_export(filepath, buf)

    def export_wsram(self, bank, filepath, bnk_number=1):
        """export wsram file"""
        bkcp = deepcopy(bank)
        link = (1, 1)
        for wseq in bkcp.wseqs:
            if len(wseq.steps) <= 1:
                link = (0, 1)
            wseq.parameters['ws_link'], wseq.parameters['ws_slink'] = link
            nsteps = len(wseq.steps)
            cnt = self._bytecnt()
            for step in wseq.steps:
                c = next(cnt)
                vals = (c, c + 2)
                if c == nsteps - 1:
                    vals = (c, 0)
                step.parameters['ws_blink'], step.parameters['ws_flink'] = vals

            fill = Step(self._parm['Step'])
            fill._limits = (self._lims['sizes']['Step'], self._lims['limits'])
            fill._rawpar = (int('ffff', 16), 0, 0, 0, 0, 0, 0, 0, 0, 0)

            wseq.steps = [fill] + wseq.steps + (255 - nsteps) * [fill]

        st, en = (bnk_number - 1) * 50, ((bnk_number - 1) * 50) + 50
        bkcp.perfs = bkcp.perfs[st:en]
        st, en = (bnk_number - 1) * 35, ((bnk_number - 1) * 35) + 35
        bkcp.patches = bkcp.patches[st:en]
        perf, patch, wseq, steps, wsnam = self._file_build(bkcp)
        head = self._blks['wshd']
        end = self._blks['40s']
        buf = head + perf + patch + wseq + steps + wsnam + end
        self._file_export(filepath, buf)

    def _pack_str(self, data, pk_str):
        qt = int(pk_str[3:]) - 1
        form = '{{0:<{0}}}\x00'.format(qt)
        name = form.format(data[:qt])
        name = name.encode('ascii')
        if name == self._h2b('20' * qt + '00'):
            name = self._h2b('0' * qt * 2)
        return self._pack(name, self._strc[pk_str])

    def _pack_part(self, data, *args):
        pk = self._strc['part']
        data = list(data)
        extra_par = data[-4:]
        par = data[:-4]
        par[4] = int(''.join(['{:02b}'.format(i) for i in extra_par]), 2)
        return self._pack(par, pk)

    def _pack_osc(self, data, *args):
        pk = self._strc['osc']
        data = list(data)
        lfo1sh, lfo1syn = data[9:11]
        lfo2sh, lfo2syn = data[19:21]
        lfo1sh = int('{0}{1}'.format(format(lfo1syn, 'b'), '{:07b}'.format(lfo1sh)), 2)
        lfo2sh = int('{0}{1}'.format(format(lfo2syn, 'b'), '{:07b}'.format(lfo2sh)), 2)
        return self._pack(data[:9] + [lfo1sh] + data[11:19] + [lfo2sh] + data[21:], pk)

    def _pack_wseq(self, data, *args):
        pk = self._strc['wseq']
        data = list(data)
        loop_count, loop_dir = data[4:6]
        loop_count = int('{0}{1}'.format(format(loop_dir, 'b'), '{:07b}'.format(loop_count)), 2)
        return self._pack(data[0:4] + [loop_count] + data[6:], pk)

    def __repr__(self):
        return '<{0} Wavestation IO Obj>'.format(self.__class__.__name__)


class FxBuilder(Base):
    def __init__(self):
        par = self._load_par(_def)['fx']
        self._names = self._key2int(par['names'])
        self._pcr = par['pcr']
        self._param = [self._key2int(d) for d in par['param']]
        self._ranges = par['ranges']
        self._default = self._key2int(par['defaults'])
        self._limits = par['limits']

    @staticmethod
    def _key2int(dic):
        return {int(k): v for k, v in dic.items()}

    def _newfx(self, fx_number, parameters=None):
        """return a new fx obj with defaut parameters set"""
        param = tuple(self._default[fx_number]) if parameters is None else parameters
        fx = Fx()
        fx.number = fx_number
        fx.group = self._get_group(fx_number)
        fx.name = self._names[fx_number][0]
        fx._parnum = self._par_numbers(fx.group)
        fx._limits = (self._limits['sizes'][fx.group], self._limits['limits'])
        fx._parnam = [self._get_parameters(fx.group)[n][0] for n in fx._parnum]  # parameters names
        fx._rawparam = param
        limits = [self._get_parameters(fx.group)[i][1] for i in fx._parnum]
        # parameters units dict index
        fx._ranges = [self._ranges[limits[i]] if limits[i] is not None else None for i in range(len(limits))]

        return fx

    def change_fx(self, fx_list, routing=None, fx1_number=None, fx2_number=None):
        """
        Change effects interface - Enter the fx (list) from Perf obj (Perf.fx) and the replacement
        effect numbers for each position and a new effect object (default parameters) will replace the previous in place
        Parameters:
        routing: int: 0 or 1 (0 Parallel Routing, 1 Series Routing)
        fx1_number, fx2_number: int: 0-55 (0 is empty effect)
        Returns: the updated list of effects objects
        warning:
        If effect 54 or 55 is selected in any position (fx1 or fx2), the other effect will be overwriten by an Empty Fx
        """
        if len(fx_list) != 3 or any([not isinstance(i, Fx) for i in fx_list]):
            raise (Exception('fx list must contain 3 effects (class Fx objects)'))

        fxdef = (routing, fx1_number, fx2_number)

        if any([i is not None and not (isinstance(i, int) and 0 <= i <= 55) for i in fxdef]):
            raise (Exception('parameters not accepted, must be integers from 0-55 or None for bypass (keep same fx)'))

        if routing is not None and 0 <= routing <= 1:
            fx_list[0] = self._newfx(routing - 2)

        if fx1_number is not None:
            if fx1_number < 54:
                fx_list[1] = self._newfx(fx1_number)
            else:
                fx_list[1] = self._newfx(fx1_number)
                fx_list[2] = self._newfx(0)

        if fx2_number is not None:
            if fx2_number < 54:
                fx_list[2] = self._newfx(fx2_number)
            else:
                fx_list[1] = self._newfx(0)
                fx_list[2] = self._newfx(fx2_number)

        return fx_list

    def _packfx(self, fxlist):
        """returns 21 bytes (binary) fx definitions from fxlist"""
        bf, fxnum = [[['0'] * 8 for _ in range(5)]] + [[['0'] * 8 for _ in range(8)]] + [
            [['0'] * 8 for _ in range(8)]], []

        for i, fx in enumerate(fxlist):
            psizsign, pcut, location = self._param_size_sign_cut(fx.number)
            pbits = []
            buf = bf[i]

            for e, p in enumerate(fx._rawparam):  # fix for signed parameters with units
                fx_gr = self._get_group(fx.number)
                has_units = self._has_units(fx_gr, fx._parnum[e])
                signed = self._is_signed(fx_gr, fx._parnum[e])
                if has_units and signed:
                    r = self._param_range(fx_gr, fx._parnum[e])
                    ran = self._signed_range(r)
                    p = ran[p]
                pbits.append(self._par2binstr(p, *psizsign[e]))

            parinfo = zip(pbits, pcut, location)
            for par, cut, loc in parinfo:
                cnt = 0
                for e, ct in enumerate(cut):
                    p = par[::-1][cnt:ct + cnt]  # reversed
                    cnt = ct
                    bl, bo = loc[e]
                    byt = buf[bl][::-1]  # also reversed
                    byt[bo:bo + len(p)] = list(p)
                    buf[bl] = byt[::-1]  # back to normal (re-reversed)
            bf[i] = buf

        for e, f in enumerate(fxlist):
            num = f.number
            if e == 0:
                if num == -1:
                    bf[0][0][0] = '1'  # series routing, parallel is 0, no need to set
            else:
                ext = num > 47
                if not ext:
                    bf[0][e - 1][2:] = list(format(num + 2, '06b'))  # 2-49
                else:
                    bf[0][e - 1][2:] = '000010'  # select 2
                    bf[0][1][0] = '1'  # extended mode set
                    bf[e][0][-3:] = list(format(num - 47, '03b'))  # 1-8 set in each fx block

        buf = [[int(''.join(j), 2) for j in i] for i in bf]
        buf = b''.join([self._byte(i) for i in buf[0] + buf[1] + buf[2]])

        return buf

    def _param_size_sign_cut(self, fx_number):
        """
        returns: lists
        [tuples - size and sign of the fx parameters],
        [tuples - size of par bits for pcr per par],
        [tuples - final placement position]
        """
        sizesign, grp, cut = [], [], []
        fxgroup = self._get_group(fx_number)

        for e, n in enumerate(self._par_numbers(fxgroup)):
            ct, gr = [], []
            for p in self._pcr[fxgroup]:
                if p[3] == n:
                    gr.append(p[2])  # par bit size
                    ct.append((p[0], p[1]))  # byte number, bit offset, param offset # leftover -->, p[4]
            grp.append(gr)
            cut.append(ct)
            sizesign.append((sum([abs(x) for x in grp[e]]), any([i < 0 for i in grp[e]])))
        return sizesign, [tuple([abs(v) for v in g]) for g in grp], cut

    def _par2binstr(self, param, size, signed):
        """return a binary string from the value, bitsize and sign of the parameter"""
        return self._signed_binstr(param, size) if signed else format(param, '0{}b'.format(size))

    def _unpackfx(self, binary):
        """receives 21 bytes fx coded parameters and return an Fx object"""

        fxbytes = bytearray(binary)  # 21 bytes
        fx0_arr, fx1_arr, fx2_arr = fxbytes[:5], fxbytes[5:13], fxbytes[13:21]  # (5b, 8b, 8b) (rout, fx1, fx2)
        fx_def_bin = [format(i, '08b') for i in fx0_arr]
        fx_routing = int(fx_def_bin[0][0])  # parallel = 0, series = 1
        fx0_number = fx_routing - 2
        fx1_number = int(fx_def_bin[0][2:], 2) - 2  # 6 bit
        fx2_number = int(fx_def_bin[1][2:], 2) - 2  # 6 bit
        fx_ext_bit = int(fx_def_bin[1][0])

        # check extended fx mode - null fx and 2nd byte, first bit (msb) set
        if fx1_number == 0 and fx_ext_bit == 1:
            fx1_number = int(format(fx1_arr[0], '08b')[-3:], 2) + 47

        if fx2_number == 0 and fx_ext_bit == 1:
            fx2_number = int(format(fx2_arr[0], '08b')[-3:], 2) + 47

        fnumbs = [fx0_number, fx1_number, fx2_number]
        fxarrs = [fx0_arr, fx1_arr, fx2_arr]

        fx = [self._buildfx(fnumbs[i], fxarrs[i]) for i in range(3)]

        check = [f.number < 0 for f in fx][1:]  # fx1 and fx2

        if any(check):  # check if is a valid effect
            empty = self._newfx(0)
            if check[0]:
                fx[1] = empty
            if check[1]:
                fx[2] = empty
            if all(check):  # disables routing
                fx[0] = empty

        return fx

    def _buildfx(self, fx_number, fx_arr):
        fx_group = self._get_group(fx_number)  # group number
        pcr_fx = self._pcr[fx_group]  # pcr select
        fx_parval = self._fx_parameters_unpack(fx_arr, pcr_fx, fx_group)  # parameters numbers and values

        return self._newfx(fx_number, fx_parval)

    def _fx_parameters_unpack(self, bytearr, pcr_list, fx_group):
        """Returns a tuple containing the effects parameters numbers and its values, ((tuple),(tuple))"""
        def lr(p0, p1): return len(range(p0, p1))

        bs = [format(i, '08b') for i in bytearr]  # binary string
        parameters = {}
        par_nums = self._par_numbers(fx_group)

        for pcr in pcr_list:
            p = self._cut_parameter(bs, pcr)  # binary string
            length, number, offset = pcr[2], pcr[3], pcr[4]
            signed = self._is_signed(fx_group, number)
            has_units = self._has_units(fx_group, number)  # signed parameters with units fix (2 params) # hack
            if has_units and signed:
                signed = False
                s, e = self._param_range(fx_group, number)
                s_ran = [i - lr(s, e) // 2 if self._ev(s, e) else i - ((lr(s, e) // 2) + 1) for i in range(s, e + 1)]
                p = s_ran.index(self._sign_int(p))
                p = format(p, '08b')

            if offset == 0:  # offset is the parameter continuation (left part)
                parameters[number] = [p, signed]
            else:
                parameters[number][0] = '{0}{1}'.format(p, parameters[number][0])

        processed = {}
        for key, v in parameters.items():  # process binary string to signed/unsigned int
            val, signed = v[0], v[1]
            value = self._sign_int(val) if signed else int(val, 2)
            processed[key] = value

        out = []
        for i in par_nums:
            out.append(processed[i])

        return tuple(out)

    @staticmethod
    def _cut_parameter(par_bin_str, pcr):
        """slices bits according to pcr"""
        return par_bin_str[pcr[0]][::-1][pcr[1]:pcr[1] + abs(pcr[2])][::-1]  # select, reverse, cut, re-reverse

    @staticmethod
    def _ev(start, end):  # even length
        return len(range(start, end)) / 2.0 == len(range(start, end)) // 2

    def _all_fx_in_group(self, fx_group):
        """group fxs in a dict {num:name}"""
        if fx_group <= 26:
            return {k: v[0] for k, v in self._names.items() if v[1] == fx_group}

    def help_all_fx_listing(self):
        def gpn(number): return self._par_numbers(self._get_group(number))

        n = self._names
        s1 = '{0}: \'{1}\' (gr {2}: {3} params)\n'
        hp = [s1.format(format(i, '02'), n[i][0], n[i][1], len(gpn(i))) for i in range(-2, 56)]
        hp.append('\nUse help_param() method to see the parameters per effect group\n')
        hp.append('All Effects in each group have the same parameters\n')
        return ''.join(hp)

    def help_fx_params_by_group(self, fx_group, vals=None, parnumber=None):
        def gu(gr, na): return self._get_units(gr, na)

        def hu(gr, na): return self._has_units(gr, na)

        def gun(fxg, num, ind): return self._get_unit(fxg, num, ind)

        if fx_group > 26:
            return 'fx group number {} not allowed (0-26)'.format(fx_group)

        fgr = fx_group
        hp = ['{0} {1}\n'.format(*i) for i in self._all_fx_in_group(fgr).items()]
        sp = ['-' * len(hp[-1]) + '\n']
        hp = sp + hp + sp
        hp.append('Parameters:\n\n')

        numb = self._par_numbers(fgr)
        if parnumber is not None and parnumber in numb:
            numb = [parnumber]
        name = [self._par_name(fgr, i) for i in numb]
        rang = [(self._param_range(fgr, i)[0], self._param_range(fgr, i)[1]) for i in numb]
        if vals:
            hd = '{} -> {}'
            itr = zip(name, numb)
            vals = [hd.format(vals[n], gun(fgr, nu, vals[n]) if gun(fgr, nu, vals[n]) else vals[n]) for n, nu in itr]
        else:
            vals = [''] * len(name)
        head = '{0}{{0}} \'{{1}}\'\n{0}'.format(sp[0])
        out = head + 'Range:{2} {3}{4}\n' if not vals else head + 'Value: {4}\nRange: {2} {3}\n'
        s1 = '\nIndex in [{}]\n'
        s2 = '\nvalues from {} to {}\n'
        enum = enumerate(numb)
        unit = [s1.format(' '.join(gu(fx_group, i))) if hu(fx_group, i) else s2.format(*rang[e]) for e, i in enum]
        hp.extend([out.format(m, n, r, u, v) for m, n, r, u, v in zip(numb, name, rang, unit, vals)])
        hp.append('Stored Parameter value must be always integer (direct value or indexing listed params values)')
        return ''.join(hp)

    def help_fx_params(self, fxobj, parnumber=None):
        return self.help_fx_params_by_group(fxobj.group, fxobj.parameters, parnumber)

    def _get_pcr(self, fx_num):
        return self._pcr[self._get_group(fx_num)]

    def _get_group(self, fx_num):
        return self._names[fx_num][1]

    def _get_parameters(self, fx_group):
        return self._param[fx_group]

    def _par_name(self, fx_group, par_num):
        return self._param[fx_group][par_num][0]

    def _par_numbers(self, fx_group):
        parnum = []
        for p in self._pcr[fx_group]:
            if p[3] not in parnum:
                parnum.append(p[3])
        return parnum

    def _param_bit_size(self, fx_group, par_num):
        """returns the parameter bit size and sign (tuple(int, bool))"""
        pcr = self._pcr[fx_group]
        lengths = [i[2] for i in pcr if i[3] == par_num]
        return sum([abs(i) for i in lengths]), any([sign for sign in map(lambda x: x < 0, lengths)])

    def _param_range(self, fx_group, par_num):
        """returns the parameter range (tuple(int, int))"""
        ranges = self._get_units(fx_group, par_num)
        if ranges:
            return 0, len(ranges) - 1
        else:
            size, signed = self._param_bit_size(fx_group, par_num)
            if signed:
                return self._sign_int('1{}'.format('0' * (size - 1))), self._sign_int('0{}'.format('1' * (size - 1)))
            else:
                return 0, int('1' * size, 2)

    def _is_signed(self, fx_group, par_num):
        return any([i < 0 for i in [pcr[2] for pcr in self._pcr[fx_group] if pcr[3] == par_num]])

    def _has_units(self, fx_group, par_num):
        return self._get_parameters(fx_group)[par_num][1] is not None

    def _get_units(self, fx_group, par_num):
        if self._has_units(fx_group, par_num):
            return self._ranges[self._get_parameters(fx_group)[par_num][1]]

    def _get_unit(self, fx_group, par_num, index):
        if self._has_units(fx_group, par_num):
            return self._get_units(fx_group, par_num)[index]

    def _signed_range(self, unsigned_range):
        def lr(p0, p1): return len(range(p0, p1))
        s, e = unsigned_range
        # fix 2 prms > neg val + uns
        return [i - lr(s, e) // 2 if self._ev(s, e) else i - ((lr(s, e) // 2) + 1) for i in range(s, e + 1)]


class Parameters(dict):
    def __init__(self, parent, dic, limits):
        self.ref = weakref.proxy(parent)
        super(Parameters, self).__init__(dic)
        self._sizes = self._expand(limits[0])  # tuple (size string, limits dic)
        self._limits = limits[1]

    def __setitem__(self, key, value):
        parnames = self.ref._parnam
        if not isinstance(value, int):
            raise (Exception('non integer value not allowed this parameter'))
        if key not in parnames:
            raise (Exception('{0} is not a parameter in {1}'.format(key, self.ref.__class__.__name__)))
        else:
            i = parnames.index(key)
            s = self._sizes[i]
            limits = self._limits[s]
            if limits[0] <= value <= limits[1]:
                super(Parameters, self).__setitem__(key, value)
                self.ref._update_pars()
            else:

                raise (Exception('value ({0}) exceeds the limits allowed for this parameter, {1}'.format(value, limits)))

    @staticmethod
    def _expand(s):
        t = ''.join(map(lambda x: x + ' ' if x.isalpha() else x, s)).split()
        return ''.join([int(i[:-1]) * i[-1] if i[0].isdigit() else i for i in t])


class WSObj(object):
    _parnam = None
    _rawpar = None
    name = None
    number = None
    parameters = {}
    _limits = None

    @property
    def _rawparam(self):
        return self._rawpar

    @_rawparam.setter
    def _rawparam(self, value):
        self._rawpar = value
        self.parameters = Parameters(self, {k: v for k, v in zip(self._parnam, self._rawpar)}, self._limits)

    def _update_pars(self):
        new_parameters = []
        for name in self._parnam:
            if name in self.parameters:
                new_parameters.append(self.parameters[name])
        self._rawpar = tuple(new_parameters)

    def __repr__(self):
        name = ': {}'.format(self.name) if self.name is not '' and self.name is not None else ''
        return '<{0} {1}{2}>'.format(self.__class__.__name__, self.number, name.rstrip())

    def __str__(self):
        if self.parameters:
            par = sorted(self.parameters.items(), key=lambda x: self._parnam.index(x[0]))
            if self.name and (self.number is not None):
                parstr = ['{0}: {1}'.format(k, v) for k, v in par]
                sep = '{0}{1}'.format((len(self.name) + len(str(self.number)) + 2) * '-', '\n')
                return '{0}: {1}\n{2}{3}\n'.format(self.number, self.name, sep, '\n'.join(parstr))
            else:
                return '\n'.join(['{0}: {1}'.format(k, v) for k, v in par])
        else:
            return '{0} {1}: {2}'.format(self.__class__.__name__, self.number, self.name.rstrip())

    def __eq__(self, other):
        return self.parameters == other.parameters

    def __deepcopy__(self, memo):
        copy = object.__new__(type(self))
        memo[id(self)] = copy
        for k, v in self.__dict__.items():
            if k is not 'parameters':
                copy.__dict__[k] = deepcopy(v, memo)
            else:
                copy.__dict__[k] = Parameters(copy, v, self._limits)
        return copy


class WSBank(object):
    def __init__(self, params):
        self.perfs = []
        self.patches = []
        self.wseqs = []
        self._par = params

    def __len__(self):
        return len(self.perfs)

    def __repr__(self):
        return '<{0}>'.format(self.__class__.__name__)

    def __str__(self):  # TODO: improve
        head = 'Wavestation Bank\n' + 16 * '-' + '\n'
        output = '{}Performances: {}\nPatches: {}\nWave Sequences: {}\nWave Steps: {}'
        steps = sum([len(s.steps) for s in self.wseqs])
        return output.format(head, len(self.perfs), len(self.patches), len(self.wseqs), steps)

    def steps(self):
        return [s.steps for s in self.wseqs]

    def help_all_params(self):
        """returns string: all bank WS structures: all parameters, index, names and descriptions"""
        struc = ['Part', 'Patch', 'OSC', 'WaveSeq', 'Step']
        out = ''
        for s in struc:
            parnames = self._par[s][0]
            pardesc = self._par[s][1]
            pidx = range(len(parnames))
            prep = 'index | {} Parameters | Descriptions:'.format(s)
            out += '{1}\n{0}\n{1}\n'.format(prep, len(prep) * '-')
            out += '\n'.join('{0:<5}{1:18}{2}'.format(i, p, d) for i, p, d in zip(pidx, parnames, pardesc))
            out += '\n\n'
        return out

    def help_parameters(self, obj):
        """returns string: all parameters for one WS structure. Parameters names, values and descriptions"""
        if not any([isinstance(obj, o) for o in [Part, Patch, OSC, WaveSeq, Step]]):
            return obj.__class__.__name__ + ' is not instance of Part or Patch or OSC or WaveSeq or Step'
        parnames = self._par[obj.__class__.__name__][0]
        pardesc = self._par[obj.__class__.__name__][1]
        pidx = range(len(parnames))
        values = obj._rawparam
        out = ''
        if values:
            pr = 'index | {1} ({0}) Parameters | Values | Descriptions:'
            prep = pr.format(obj.name.rstrip() if obj.name else '', obj.__class__.__name__)
            out += '{1}\n{0}\n{1}\n'.format(prep, len(prep) * '-')
            pvd = zip(pidx, parnames, values, pardesc)
            out += '\n'.join('{0:<5}{1:18}{2:<10}{3:20}'.format(i, p, v, d) for i, p, v, d in pvd)
            out += '\n'
            return out

    def help_param_by_index(self, obj, par_index):
        """Return string: single parameter name, value and description by its structure and index"""
        if not any([isinstance(obj, o) for o in [Part, Patch, OSC, WaveSeq, Step]]):
            return obj.__class__.__name__ + ' is not instance of Part or Patch or OSC or WaveSeq or Step'
        parname, pardesc = self._get_par_desc(obj, par_index)
        value = obj._rawparam[par_index]
        if value:
            return '{0:18}{1:<10}{2:20}'.format(parname, value, pardesc)

    def help_fx_params_by_number(self, perf_number, fx_index):
        if fx_index > 2 or fx_index < 0 or perf_number not in range(len(self.perfs)):
            return 'parameter out of range'
        fxobj = self.perfs[perf_number].fx[fx_index]
        fxb = FxBuilder()
        return fxb.help_fx_params_by_group(fxobj.group, fxobj.parameters)

    @ staticmethod
    def help_fx_params(fxobj, parnumber=None):
        fxb = FxBuilder()
        return fxb.help_fx_params(fxobj, parnumber)

    def _get_par_desc(self, obj, index):
        """return tuple with strings: one param name and the description by index"""
        if not any([isinstance(obj, o) for o in [Part, Patch, OSC, WaveSeq, Step]]):
            return obj.__class__.__name__ + ' is not instance of Part or Patch or OSC or WaveSeq or Step'
        parname = self._par[obj.__class__.__name__][0][index]
        pardesc = self._par[obj.__class__.__name__][1][index]
        return parname, pardesc


class Perf(WSObj):
    def __init__(self, par_names=None):
        self._parnam = par_names
        self.fx = None
        self.parts = []


class Fx(WSObj):
    def __init__(self):
        self.number = None
        self.group = None
        self.name = None
        self.parameters = None
        self._parnam = None
        self._parnum = None
        self._ranges = None

    def get_param_size(self, par_num):
        i = self.par_index(par_num)
        r = self._ranges[i]
        return (0, len(r) - 1) if r else tuple(self.parameters._limits[self.parameters._sizes[i]])

    def get_param_units(self, par_num):
        i = self.par_index(par_num)
        r = self._ranges[i]
        if not r:
            lims = self.parameters._limits
            un = lims[self.parameters._sizes[i]]
            return range(un[0], un[1] + 1)
        return r

    def par_index(self, par_num):
        return self._parnum.index(par_num)

    def get_param_num(self, par_name):
        if par_name in self._parnam:
            return self._parnum[self._parnam.index(par_name)]

    def is_index(self, par_num):
        return self.get_ranges(self.par_index(par_num)) is not None

    def get_ranges(self, par_index):
        return self._ranges[par_index]

    def __str__(self):

        def gpn(p): return self.get_param_num(p)

        if not self.parameters:
            return

        iterat = self.parameters.items()
        par = [(k, self.get_ranges(self.par_index(gpn(k)))[v]) if self.is_index(gpn(k)) else (k, v) for k, v in iterat]
        par = sorted(par, key=lambda x: self._parnam.index(x[0]))
        pr = ['{0}: {1}'.format(k, v) for k, v in par]
        st = '{0}: {1}\n{2}\n'
        return st.format(self.number, self.name, (len(self.name) + len(str(self.number)) + 2) * '-') + '\n'.join(pr)


class Part(WSObj):
    def __init__(self, par_names):
        self._parnam = par_names


class Patch(WSObj):
    def __init__(self, par_names):
        self._parnam = par_names
        self.osc = []


class OSC(WSObj):
    def __init__(self, par_names):
        self._parnam = par_names

    def __repr__(self):
        return '<OSC {0}>'.format(self.number)


class WaveSeq(WSObj):
    def __init__(self, par_names):
        self._parnam = par_names
        self.steps = []


class Step(WSObj):
    def __init__(self, par_names):
        self._parnam = par_names

if __name__ == '__main__':
    a = WSIO()
    b = a.load_bank(os.getcwd() + '\\tests\\factory.syx')
    print(b)
