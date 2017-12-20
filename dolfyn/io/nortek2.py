from struct import unpack
import nortek2_defs as defs
import nortek2lib as lib
from ..adp.base import adcp_raw, adcp_config
reload(defs)    


# TODO
######
# - Add ensemble counter

class Ad2cpReader(object):
    debug = False

    def __init__(self, fname, endian=None, bufsize=None, rebuild_index=False):

        self.fname = fname
        self._check_nortek(endian)
        self.reopen(bufsize)
        self._index = lib.get_index(fname,
                                    reload=rebuild_index)
        self._ens_pos = lib.index2ens_pos(self._index)
        self._config = lib.calc_config(self._index)
        self._init_burst_readers()
        self.unknown_ID_count = {}

    def _init_burst_readers(self, ):
        self._burst_readers = {}
        for rdr_id, cfg in self._config.items():
            self._burst_readers[rdr_id] = defs.calc_burst_struct(
                cfg['_config'], cfg['nbeams'], cfg['ncells'])

    def init_data(self, nens):
        outdat = {}
        for ky in self._burst_readers:
            outdat[ky] = self._burst_readers[ky].init_data(nens)
        return outdat

    def read_hdr(self, do_cs=False):
        res = defs._header.read2dict(self.f, cs=do_cs)
        if res['sync'] != 165:
            raise Exception("Out of sync!")
        return res

    def _check_nortek(self, endian):
        self.reopen(10)
        byts = self.f.read(2)
        if endian is None:
            if unpack('<' + 'BB', byts) == (165, 10):
                endian = '<'
            elif unpack('>' + 'BB', byts) == (165, 10):
                endian = '>'
            else:
                raise Exception(
                    "I/O error: could not determine the 'endianness' "
                    "of the file.  Are you sure this is a Nortek "
                    "AD2CP file?")
        self.endian = endian

    def reopen(self, bufsize=None):
        if bufsize is None:
            bufsize = 1000000
        try:
            self.f.close()
        except AttributeError:
            pass
        self.f = open(self.fname, 'rb', bufsize)

    def readfile(self, ens_start=0, ens_stop=None):
        nens_total = len(self._ens_pos)
        if ens_stop is None or ens_stop > nens_total:
            ens_stop = nens_total - 1
        nens = ens_stop - ens_start
        outdat = self.init_data(nens)
        print('Reading file %s ...' % self.fname)
        retval = None
        c = 0
        if ens_start > 0:
            self.f.seek(self._ens_pos[ens_start], 0)
        while not retval:
            try:
                hdr = self.read_hdr()
            except IOError:
                return outdat
            id = hdr['id']
            if id in [21, 24]:
                self.read_burst(id, outdat[id], c)
            else:
                # 0xa0 (i.e., 160) is a 'string data record',
                # according to the AD2CP manual
                # Need to catch the string at some point...
                if id not in self.unknown_ID_count:
                    self.unknown_ID_count[id] = 1
                    print('Unknown ID: {:02X}'.format(id))
                else:
                    self.unknown_ID_count[id] += 1
                self.f.seek(hdr['sz'], 1)
            # It's unfortunate that all of this count checking is so
            # complex, but this is the best I could right now.
            if c + ens_start + 1 >= nens_total:
                # Make sure we're not at the end of the count list.
                continue
            while (self.f.tell() >= self._ens_pos[c + ens_start + 1]):
                c += 1
                if c + ens_start + 1 >= nens_total:
                    # Again check end of count list
                    break
            if c >= nens:
                return outdat

    def read_burst(self, id, dat, c, echo=False):
        rdr = self._burst_readers[id]
        rdr.read_into(self.f, dat, c)

    def sci_data(self, dat):
        for id in dat:
            dnow = dat[id]
            rdr = self._burst_readers[id]
            rdr.sci_data(dnow)
            if 'vel' in dnow and 'vel_scale' in dnow:
                dnow['vel'] = (dnow['vel'] *
                               10.0 ** dnow['vel_scale']).astype('float32')

    def __exit__(self, type, value, trace,):
        self.f.close()

    def __enter__(self,):
        return self


def reorg(dat):
    outdat = adcp_raw()
    cfg = outdat['config'] = adcp_config('Nortek AD2CP')
    outdat.groups.add('config', 'config')

    for id, tag in [(21, ''), (24, '_b5')]:
        if id not in dat:
            continue
        dnow = dat[id]
        cfg['burst_config' + tag] = lib.headconfig_int2dict(
            lib.collapse(dnow['config']))
        outdat['mpltime' + tag] = lib.calc_time(
            dnow['year'] + 1900,
            dnow['month'],
            dnow['day'],
            dnow['hour'],
            dnow['minute'],
            dnow['second'],
            dnow['usec100'].astype('uint32') * 100)
        outdat.groups.add('mpltime' + tag, '_essential')
        tmp = lib.beams_cy_int2dict(
            lib.collapse(dnow['beam_config']), 21)
        cfg['ncells' + tag] = tmp['ncells']
        cfg['coord_sys' + tag] = tmp['cy']
        cfg['nbeams' + tag] = tmp['nbeams']
        for ky in ['SerialNum', 'cell_size', 'blanking',
                   'nom_corr', 'data_desc',
                   'vel_scale', 'power_level']:
            # These ones should 'collapse'
            # (i.e., all values should be the same)
            # So we only need that one value.
            cfg[ky + tag] = lib.collapse(dnow[ky])
        for ky in ['c_sound', 'temp', 'press',
                   'heading', 'pitch', 'roll',
                   'temp_press', 'batt_V',
                   'temp_mag', 'temp_clock',
                   'Mag', 'Acc',
                   'ambig_vel', 'xmit_energy',
                   'error', 'status0', 'status', 'ensemble']:
            # No if statement here
            outdat[ky + tag] = dnow[ky]
        for ky in [
                'vel', 'amp', 'corr',
                'alt_dist', 'alt_quality', 'alt_status',
                'ast_dist', 'ast_quality', 'ast_offset_time',
                'ast_pressure',
                'altraw_nsamp', 'altraw_dist', 'altraw_samp',
                'echo',
                'orientmat', 'ahrs_gyro',
                'percent_good',
                'std_pitch', 'std_roll', 'std_heading', 'std_press'
        ]:
            if ky in dnow:
                outdat[ky + tag] = dnow[ky]
        for grp, keys in defs._burst_group_org.items():
            for ky in keys:
                if ky + tag in outdat:
                    outdat.groups.add(ky + tag, grp)
    outdat.props['coord_sys'] = cfg['coord_sys']
    return outdat


def reduce(data):
    for ky in ['mpltime',
               'c_sound', 'temp', 'press',
               'temp_press', 'temp_clock', 'temp_mag', 'batt_V',
               'ensemble']:
        lib.reduce_by_average(data, ky, ky + '_b5')

    for ky in ['heading', 'pitch', 'roll']:
        lib.reduce_by_average_angle(data, ky, ky + '_b5')


if __name__ == '__main__':

    rdr = Ad2cpReader('../../example_data/BenchFile01.ad2cp')
    rdr.readfile()
