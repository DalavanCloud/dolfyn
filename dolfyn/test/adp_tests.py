import dolfyn.adp.api as apm
import dolfyn.data.base
from base import ResourceFilename

rfnm = ResourceFilename('dolfyn.test')

dolfyn.data.base.debug_level = 1

dat_rdi = apm.load(rfnm('data/RDI_test01.h5'), 'ALL')
dat_rdi_i = apm.load(rfnm('data/RDI_test01_rotate_beam2inst.h5'), 'ALL')
dat_awac = apm.load(rfnm('data/AWAC_test01.h5'), 'ALL')
dat_sig = apm.load(rfnm('data/BenchFile01.h5'), 'ALL')
dat_wr1 = apm.load(rfnm('data/winriver01.h5'), 'ALL')
dat_wr2 = apm.load(rfnm('data/winriver02.h5'), 'ALL')


def data_equiv(dat1, dat2, message=''):
    assert dat1 == dat2, message


def read_test(make_data=False):

    td_rdi = apm.read_rdi(rfnm('data/RDI_test01.000'))
    td_sig = apm.read_signature(rfnm('data/BenchFile01.ad2cp'))
    td_awac = apm.read_nortek(rfnm('data/AWAC_test01.wpr'))
    td_wr1 = apm.read_rdi(rfnm('data/winriver01.PD0'))
    td_wr2 = apm.read_rdi(rfnm('data/winriver02.PD0'))

    if make_data:
        td_rdi.save(rfnm('data/RDI_test01.h5'))
        td_sig.save(rfnm('data/BenchFile01.h5'))
        td_awac.save(rfnm('data/AWAC_test01.h5'))
        td_wr1.save(rfnm('data/winriver01.h5'))
        td_wr2.save(rfnm('data/winriver02.h5'))
        return

    msg_form = "The output of read_rdi('{}') does not match '{}'."
    for dat1, dat2, msg in [
            (td_rdi, dat_rdi,
             msg_form.format('RDI_test01.000', 'RDI_test01.h5')),
            (td_sig, dat_sig,
             msg_form.format('BenchFile01.ad2cp', 'BenchFile01.h5')),
            (td_awac, dat_awac,
             msg_form.format('AWAC_test01.wpr', 'AWAC_test01.h5')),
            (td_wr1, dat_wr1,
             msg_form.format('winriver01.PD0', 'winriver01.h5')),
            (td_wr2, dat_wr2,
             msg_form.format('winriver02.PD0', 'winriver02.h5')),
    ]:
        yield data_equiv, dat1, dat2, msg


def rotate_beam2inst_test(make_data=False):

    td = dat_rdi.copy()
    apm.beam2inst(td)

    if make_data:
        td.save(rfnm('data/RDI_test01_rotate_beam2inst.h5'))
        return

    assert td == dat_rdi_i, "adp.rotate.beam2inst gives unexpected results!"


def rotate_inst2earth_test(make_data=False):

    td = dat_rdi_i.copy()
    apm.inst2earth(td)
    tdwr2 = dat_wr2.copy()
    apm.inst2earth(tdwr2)

    if make_data:
        td.save(rfnm('data/RDI_test01_rotate_inst2earth.h5'))
        tdwr2.save(rfnm('data/winriver02_rotate_ship2earth.h5'))
        return

    cd = apm.load(rfnm('data/RDI_test01_rotate_inst2earth.h5'), 'ALL')
    cdwr2 = apm.load(rfnm('data/winriver02_rotate_ship2earth.h5'), 'ALL')

    assert td == cd, "adp.rotate.inst2earth gives unexpected results!"
    assert tdwr2 == cdwr2, "adp.rotate.inst2earth gives unexpected results!"


if __name__ == '__main__':
    import dolfyn.data.base
    dolfyn.data.base.debug_level = 10

    for func, dat1, dat2, msg in read_test():
        func(dat1, dat2, msg)
