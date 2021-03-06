from __future__ import division
import numpy as np
from ..tools.psd import psd_freq, cohere, psd, cpsd_quasisync, \
    cpsd, phase_angle
from ..tools.misc import slice1d_along_axis, detrend
from .base import ma, TimeData
import copy
import warnings
import six


class TimeBinner(object):

    def calc_omega(self, fs=None, coh=False):
        """
        Calculate the radial-frequency vector for the psd's.

        Parameters
        ----------
        fs : float (optional)
          The sample rate (Hz).
        coh : bool
          Calculate the frequency vector for coherence/cross-spectra
          (default: False) i.e. use self.n_fft_coh instead of
          self.n_fft.
        """
        n_fft = self.n_fft
        freq_dim = 'freq'
        fs = self._parse_fs(fs)
        if coh:
            n_fft = self.n_fft_coh
            freq_dim = 'coh_freq'
        dat = ma.marray(psd_freq(n_fft, fs * 2 * np.pi),
                        ma.varMeta('\omega', {'s': -1}, [freq_dim]))
        return dat

    def _outshape(self, inshape, n_pad=0, n_bin=None):
        """
        Returns `outshape` (the 'reshape'd shape) for an `inshape` array.
        """
        n_bin = int(self._parse_nbin(n_bin))
        return list(inshape[:-1]) + [inshape[-1] // n_bin, n_bin + n_pad]

    def _outshape_fft(self, inshape, n_fft=None, n_bin=None):
        """
        Returns `outshape` (the fft 'reshape'd shape) for an `inshape` array.
        """
        n_fft = self._parse_nfft(n_fft)
        n_bin = self._parse_nbin(n_bin)
        return list(inshape[:-1]) + [inshape[-1] // n_bin, n_fft // 2]

    def _parse_fs(self, fs=None):
        if fs is not None:
            return fs
        return self.fs

    def _parse_nbin(self, n_bin=None):
        if n_bin is None:
            return self.n_bin
        return n_bin

    def _parse_nfft(self, n_fft=None):
        if n_fft is None:
            return self.n_fft
        return n_fft

    def reshape(self, arr, n_pad=0, n_bin=None):
        """
        Reshape the array `arr` to shape (...,n,n_bin+n_pad).

        Parameters
        ----------
        arr : np.ndarray
        n_pad : int
          Is used to add `n_pad`/2 points from the end of the previous
          ensemble to the top of the current, and `n_pad`/2 points
          from the top of the next ensemble to the bottom of the
          current.  Zeros are padded in the upper-left and lower-right
          corners of the matrix (beginning/end of timeseries).  In
          this case, the array shape will be (...,`n`,`n_pad`+`n_bin`)
        n_bin : float, int (optional)
          Override this binner's n_bin.

        Notes
        -----
        `n_bin` can be non-integer, in which case the output array
        size will be `n_pad`+`n_bin`, and the decimal will
        cause skipping of some data points in `arr`.  In particular,
        every mod(`n_bin`,1) bins will have a skipped point. For
        example:
        - for n_bin=2048.2 every 1/5 bins will have a skipped point.
        - for n_bin=4096.9 every 9/10 bins will have a skipped point.

        """
        n_bin = self._parse_nbin(n_bin)
        npd0 = n_pad // 2
        npd1 = (n_pad + 1) // 2
        shp = self._outshape(arr.shape, n_pad=0, n_bin=n_bin)
        out = np.zeros(
            self._outshape(arr.shape, n_pad=n_pad, n_bin=n_bin),
            dtype=arr.dtype)
        if np.mod(n_bin, 1) == 0:
            # If n_bin is an integer, we can do this simply.
            out[..., npd0: n_bin + npd0] = (
                arr[..., :(shp[-2] * shp[-1])]).reshape(shp, order='C')
        else:
            inds = (np.arange(np.prod(shp[-2:])) * n_bin // int(n_bin)
                    ).astype(int)
            out[..., npd0:int(n_bin) + npd0] = (arr[..., inds]
                                                ).reshape(shp, order='C')
            # n_bin needs to be int for the n_pad operation.
            n_bin = int(n_bin)
        if n_pad != 0:
            out[..., 1:, :npd0] = out[..., :-1, n_bin:n_bin + npd0]
            out[..., :-1, -npd1:] = out[..., 1:, npd0:npd0 + npd1]
        if isinstance(arr, np.ma.MaskedArray):
            out = np.ma.masked_where(self.reshape(arr.mask,
                                                  n_pad=n_pad,
                                                  n_bin=n_bin),
                                     out)
        if ma.valid and isinstance(out, ma.marray):
            out.meta.dim_names += ['time2']
        return out

    def detrend(self, dat, n_pad=0, n_bin=None):
        """
        Reshape the array `dat` and remove the best-fit trend line.

        ... Need to fix this to deal with NaNs...
        """
        return detrend(self.reshape(dat, n_pad=n_pad, n_bin=n_bin), axis=-1)

    def demean(self, dat, n_pad=0, n_bin=None):
        """
        Reshape the array `dat` and remove the mean from each ensemble.
        """
        dt = self.reshape(dat, n_pad=n_pad, n_bin=n_bin)
        return dt - (dt.mean(-1)[..., None])

    def mean(self, dat, axis=-1, n_bin=None, mask_thresh=None):
        """Average an array object.

        Parameters
        ----------
        n_bin : int (default is self.n_bin)

        mask_thresh : float (between 0 and 1)
            if the input data is a masked array, and mask_thresh is
            not None mask the averaged values where the fraction of
            bad points is greater than mask_thresh
        """
        # Can I turn this 'swapaxes' stuff into a decorator?
        if axis != -1:
            dat = np.swapaxes(dat, axis, -1)
        n_bin = self._parse_nbin(n_bin)
        tmp = self.reshape(dat, n_bin=n_bin)
        out = tmp.mean(-1)
        if isinstance(dat, np.ma.MaskedArray) and mask_thresh is not None:
            out.mask = tmp.mask.sum(-1).astype(np.float) > mask_thresh * n_bin
        if axis != -1:
            np.swapaxes(out, axis, -1)
        if dat.__class__ is np.ndarray:
            return out
        return out.view(dat.__class__)

    def mean_angle(self, dat, axis=-1, units='radians',
                   n_bin=None, mask_thresh=None):
        """Average an angle array.

        Parameters
        ----------
        units : {'radians' | 'degrees'}

        n_bin : int (default is self.n_bin)

        mask_thresh : float (between 0 and 1)
            if the input data is a masked array, and mask_thresh is
            not None mask the averaged values where the fraction of
            bad points is greater than mask_thresh
        """
        if units.lower().startswith('deg'):
            dat = dat * np.pi / 180
        elif units.lower().startswith('rad'):
            pass
        else:
            raise ValueError("Units must be either 'rad' or 'deg'.")
        return np.angle(self.mean(np.exp(1j * dat)))

    def var(self, dat, n_bin=None):
        return self.reshape(dat, n_bin=n_bin).var(-1)

    def std(self, dat, n_bin=None):
        return self.reshape(dat, n_bin=n_bin).std(-1)

    def calc_acov(self, indat, n_bin=None):
        """
        Calculate the auto-covariance of the raw-signal `indat`.

        As opposed to calc_xcov, which returns the full
        cross-covariance between two arrays, this function only
        returns a quarter of the full auto-covariance. It computes the
        auto-covariance over half of the range, then averages the two
        sides (to return a 'quartered' covariance).

        This has the advantage that the 0 index is actually zero-lag.

        """
        n_bin = self._parse_nbin(n_bin)
        out = np.empty(self._outshape(indat.shape, n_bin=n_bin)[:-1] +
                       [n_bin // 4], dtype=indat.dtype)
        dt1 = self.reshape(indat, n_pad=n_bin / 2 - 2)
        # Here we de-mean only on the 'valid' range:
        dt1 = dt1 - dt1[..., :, (n_bin // 4):(-n_bin // 4)].mean(-1)[..., None]
        dt2 = self.demean(indat)  # Don't pad the second variable.
        dt2 = dt2 - dt2.mean(-1)[..., None]
        se = slice(int(n_bin // 4) - 1, None, 1)
        sb = slice(int(n_bin // 4) - 1, None, -1)
        for slc in slice1d_along_axis(dt1.shape, -1):
            tmp = np.correlate(dt1[slc], dt2[slc], 'valid')
            # The zero-padding in reshape means we compute coherence
            # from one-sided time-series for first and last points.
            if slc[-2] == 0:
                out[slc] = tmp[se]
            elif slc[-2] == dt2.shape[-2] - 1:
                out[slc] = tmp[sb]
            else:
                # For the others we take the average of the two sides.
                out[slc] = (tmp[se] + tmp[sb]) / 2
        return out

    def calc_lag(self, npt=None, one_sided=False):
        if npt is None:
            npt = self.n_bin
        if one_sided:
            return np.arange(npt // 2, dtype=np.float32)
        else:
            return np.arange(npt, dtype=np.float32) - npt // 2

    def calc_xcov(self, indt1, indt2, npt=None,
                  n_bin1=None, n_bin2=None, normed=False):
        """
        Calculate the cross-covariance between arrays indt1 and indt2
        for each bin.
        """
        n_bin1 = self._parse_nbin(n_bin1)
        n_bin2 = self._parse_nbin(n_bin2)
        shp = self._outshape(indt1.shape, n_bin=n_bin1)
        shp[-2] = min(shp[-2], self._outshape(indt2.shape, n_bin=n_bin2)[-2])
        out = np.empty(shp[:-1] + [npt], dtype=indt1.dtype)
        tmp = int(n_bin2) - int(n_bin1) + npt
        dt1 = self.reshape(indt1, n_pad=tmp - 1, n_bin=n_bin1)
        # Note here I am demeaning only on the 'valid' range:
        dt1 = dt1 - dt1[..., :, (tmp // 2):(-tmp // 2)].mean(-1)[..., None]
        # Don't need to pad the second variable:
        dt2 = self.demean(indt2, n_bin=n_bin2)
        dt2 = dt2 - dt2.mean(-1)[..., None]
        for slc in slice1d_along_axis(shp, -1):
            out[slc] = np.correlate(dt1[slc], dt2[slc], 'valid')
        if normed:
            out /= (self.std(indt1, n_bin=n_bin1)[..., :shp[-2]] *
                    self.std(indt2, n_bin=n_bin2)[..., :shp[-2]] *
                    n_bin2)[..., None]
        return out

    def do_avg(self, rawdat, outdat=None, names=None, n_time=None):
        """

        Parameters
        ----------
        rawdat : raw_data_object
           The raw data structure to be binned
        outdat : avg_data_object
           The bin'd (output) data object to which averaged data is added.
        names : list of strings
           The names of variables to be averaged.  If `names` is None,
           all data in `rawdat` will be binned.

        """
        props = {}
        if n_time is None:
            n_time = rawdat.n_time
        if outdat is None:
            outdat = type(rawdat)()
            props['n_bin'] = self.n_bin
            props['n_fft'] = self.n_fft
        if names is None:
            names = rawdat.keys()
        for ky in names:
            if isinstance(ky, six.string_types) and '.' in ky:
                g, nm = ky.split('.', 1)
                if g not in outdat:
                    outdat[g] = type(rawdat[g])()
                outdat[g][nm] = self.mean(rawdat[g][nm],
                                          axis=rawdat[g]._time_dim)
            elif isinstance(rawdat[ky], TimeData):
                outdat[ky] = TimeData()
                self.do_avg(rawdat[ky], outdat[ky], n_time=n_time)
            elif (isinstance(rawdat[ky], np.ndarray) and
                  rawdat[ky].shape[rawdat._time_dim] == n_time):
                outdat[ky] = self.mean(rawdat[ky], axis=rawdat._time_dim)
            else:
                outdat[ky] = copy.deepcopy(rawdat[ky])
        if 'props' in outdat:
            outdat['props'].update(props)
        return outdat

    def do_var(self, rawdat, outdat=None, names=None, suffix='_var'):
        """Calculate the variance of data attributes.

        Parameters
        ----------
        rawdat : raw_data_object
           The raw data structure to be binned.

        outdat : avg_data_object
           The bin'd (output) data object to which variance data is added.

        names : list of strings
           The names of variables of which to calculate variance.  If
           `names` is None, all data in `rawdat` will be binned.

        """
        if outdat is None:
            outdat = TimeData()
        if names is None:
            names = rawdat.keys()
        for ky in names:
            if isinstance(rawdat[ky], TimeData):
                outdat[ky] = TimeData()
                self.do_avg(rawdat[ky], outdat[ky])
            elif isinstance(rawdat[ky], np.ndarray):
                outdat[ky] = self.reshape(rawdat[ky]).var(-1)
            else:
                outdat[ky] = copy.deepcopy(rawdat[ky])
        return outdat

    def __init__(self, n_bin, fs, n_fft=None, n_fft_coh=None):
        """
        Initialize an averaging object.

        Parameters
        ----------
        n_bin : int
          the number of data points to include in a 'bin' (average).
        n_fft : int
          the number of data points to use for fft (`n_fft`<=`n_bin`).
          Default: `n_fft`=`n_bin`
        n_fft_coh : int
          the number of data points to use for coherence and cross-spectra ffts
          (`n_fft_coh`<=`n_bin`). Default: `n_fft_coh`=`n_bin`/6
        """
        self.n_bin = n_bin
        self.fs = fs
        self.n_fft = n_fft
        self.n_fft_coh = n_fft_coh
        if n_fft is None:
            self.n_fft = n_bin
        elif n_fft > n_bin:
            self.n_fft = n_bin
            print("n_fft larger than n_bin \
            doesn't make sense, setting n_fft=n_bin")
        if n_fft_coh is None:
            self.n_fft_coh = self.n_bin // 6
        elif n_fft_coh >= n_bin:
            self.n_fft_coh = n_bin // 6
            print("n_fft_coh must be smaller than n_bin, "
                  "setting n_fft_coh=n_bin / 6")

    def _check_indata(self, rawdat):
        if np.any(np.array(rawdat.shape) == 0):
            raise RuntimeError(
                "The input data cannot be averaged "
                "because it is empty.")
        if 'DutyCycle_NBurst' in rawdat.props and \
           rawdat.props['DutyCycle_NBurst'] < self.n_bin:
            warnings.warn(
                "The averaging interval (n_bin = {}) is "
                "larger than the burst interval (NBurst = {})!"
                .format(self.n_bin, rawdat.props['DutyCycle_NBurst']))
        if rawdat['props']['fs'] != self.fs:
            raise Exception(
                "The input data sample rate (dat.fs) does not "
                "match the sample rate of this binning-object!")

    def cohere(self, dat1, dat2, window='hann', debias=True,
               noise=(0, 0), n_fft=None, n_bin1=None, n_bin2=None,):
        """
        Calculate coherence between `dat1` and `dat2`.
        """
        if n_fft is None:
            n_fft = self.n_fft_coh
        n_bin1 = self._parse_nbin(n_bin1)
        n_bin2 = self._parse_nbin(n_bin2)
        oshp = self._outshape_fft(dat1.shape, n_fft=n_fft, n_bin=n_bin1)
        oshp[-2] = np.min([oshp[-2], dat2.shape[-1] // n_bin2])
        out = np.empty(oshp, dtype=dat1.dtype)
        # The data is detrended in psd, so we don't need to do it here.
        dat1 = self.reshape(dat1, n_pad=n_fft, n_bin=n_bin1)
        dat2 = self.reshape(dat2, n_pad=n_fft, n_bin=n_bin2)
        for slc in slice1d_along_axis(out.shape, -1):
            out[slc] = cohere(dat1[slc], dat2[slc],
                              n_fft, debias=debias, noise=noise)
        return out

    def cpsd(self, dat1, dat2, fs=None, window='hann',
             n_fft=None, n_bin1=None, n_bin2=None,):
        """
        Calculate the 'cross power spectral density' of `dat`.

        Parameters
        ----------
        dat1    : np.ndarray
          The first raw-data array of which to calculate the cpsd.
        dat2    : np.ndarray
          The second raw-data array of which to calculate the cpsd.
        window : string
          String indicating the window function to use (default: 'hanning').

        Returns
        -------
        out : np.ndarray
          The cross-spectral density of `dat1` and `dat2`

        """
        fs = self._parse_fs(fs)
        if n_fft is None:
            n_fft = self.n_fft_coh
        n_bin1 = self._parse_nbin(n_bin1)
        n_bin2 = self._parse_nbin(n_bin2)
        oshp = self._outshape_fft(dat1.shape, n_fft=n_fft, n_bin=n_bin1)
        oshp[-2] = np.min([oshp[-2], dat2.shape[-1] // n_bin2])
        # The data is detrended in psd, so we don't need to do it here:
        dat1 = self.reshape(dat1, n_pad=n_fft)
        dat2 = self.reshape(dat2, n_pad=n_fft)
        out = np.empty(oshp, dtype='c{}'.format(dat1.dtype.itemsize * 2))
        if dat1.shape == dat2.shape:
            cross = cpsd
        else:
            cross = cpsd_quasisync
        for slc in slice1d_along_axis(out.shape, -1):
            # PSD's are computed in radian units:
            out[slc] = cross(dat1[slc], dat2[slc], n_fft,
                             2 * np.pi * fs, window=window)
        return out

    def phase_angle(self, dat1, dat2, window='hann',
                    n_fft=None, n_bin1=None, n_bin2=None,):
        """
        Calculate the phase difference between two signals as a
        function of frequency (complimentary to coherence).

        Parameters
        ----------
        dat1    : np.ndarray
          The first raw-data array of which to calculate the cpsd.
        dat2    : np.ndarray
          The second raw-data array of which to calculate the cpsd.
        window : string
          String indicating the window function to use (default: 'hanning').

        Returns
        -------
        out : np.ndarray
          The phase difference between signal dat1 and dat2.
        """
        if n_fft is None:
            n_fft = self.n_fft_coh
        n_bin1 = self._parse_nbin(n_bin1)
        n_bin2 = self._parse_nbin(n_bin2)
        oshp = self._outshape_fft(dat1.shape, n_fft=n_fft, n_bin=n_bin1)
        oshp[-2] = np.min([oshp[-2], dat2.shape[-1] // n_bin2])
        # The data is detrended in psd, so we don't need to do it here:
        dat1 = self.reshape(dat1, n_pad=n_fft)
        dat2 = self.reshape(dat2, n_pad=n_fft)
        out = np.empty(oshp, dtype='c{}'.format(dat1.dtype.itemsize * 2))
        for slc in slice1d_along_axis(out.shape, -1):
            # PSD's are computed in radian units:
            out[slc] = phase_angle(dat1[slc], dat2[slc], n_fft,
                                   window=window)
        return out

    def psd(self, dat, fs=None, window='hann', noise=0,
            n_bin=None, n_fft=None, step=None, n_pad=None):
        """
        Calculate 'power spectral density' of `dat`.

        Parameters
        ----------
        dat    : data_object
          The raw-data array of which to calculate the psd.
        window : string
          String indicating the window function to use (default: 'hanning').
        noise  : float
          The white-noise level of the measurement (in the same units
          as `dat`).

        """
        fs = self._parse_fs(fs)
        n_bin = self._parse_nbin(n_bin)
        n_fft = self._parse_nfft(n_fft)
        if n_pad is None:
            n_pad = min(n_bin - n_fft, n_fft)
        out = np.empty(self._outshape_fft(dat.shape, n_fft=n_fft, n_bin=n_bin))
        # The data is detrended in psd, so we don't need to do it here.
        dat = self.reshape(dat, n_pad=n_pad)
        for slc in slice1d_along_axis(dat.shape, -1):
            # PSD's are computed in radian units:
            out[slc] = psd(dat[slc], n_fft, 2 * np.pi * fs,
                           window=window, step=step)
        if ma.valid and ma.marray in dat.__class__.__mro__:
            out = ma.marray(
                out,
                ma.varMeta('S(%s)' % dat.meta.name,
                           ma.unitsDict({'s': 1}) * dat.meta._units**2,
                           dim_names=dat.meta.dim_names[:-1] + ['freq'])
                )
            # The dat.meta.dim_names[:-1] drops the 'time2' dim_name.

        if noise != 0:
            # the two in 2*np.pi cancels with the two in 'self.fs/2':
            out -= noise**2 / (np.pi * fs)
            # Make sure all values of the PSD are >0 (but still small):
            out[out < 0] = np.min(np.abs(out)) / 100
        return out
