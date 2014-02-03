import numpy as np
from matplotlib.mlab import detrend_linear as detrend
fft=np.fft.fft

def psd_freq(nfft,fs):
    """
    Compute the frequency spectrum for use with psd.
    *fs* is the sampling frequency.
    """
    fs=np.float64(fs)
    return np.arange(fs/nfft,fs/2+fs/nfft,fs/nfft)


def _stepsize(l,nfft,nens=None,step=None):
    """
    Calculates the fft-step size for a length *l* array.

    If nens is None, the step size is chosen to maximize data use,
    minimize nens and have a minimum of 50% overlap.

    If nens is specified, the step-size is computed directly.

    Parameters
    ----------
    l       : The length of the array.
    nfft    : The number of points in the fft.
    nens : The number of nens to perform (default compute this).

    Returns
    -------
    step    : The step size.
    nens    : The number of ensemble ffts to average together.
    nfft    : The number of points in the fft (set to l if nfft>l).
    """
    if l<nfft:
        nfft=l
    if nens is None and step is None:
        nens=int(2.*l/nfft)
        return int((l-nfft)/(nens-1)),nens,nfft
    elif nens is None:
        return int(step),int((l-nfft)/step+1),nfft
    else:
        if nens==1:
            return 0,1,nfft
        return int((l-nfft)/(nens-1)),nens,nfft


def cohere(a,b,nfft,window='hann',debias=True,noise=(0,0)):
    """
    Computes the magnitude-squared coherence of *a* and *b*:
    
                    |S_{ab}|^2
         C_{ab} = --------------
                   S_aa * S_bb

    Here S_xy, S_xx and S_yy are the cross, and auto spectral
    densities of the signal a and b.

    *debias* specify whether to debias the signal (Benignus1969).

    The *noise* keyword may be used to specify the signals'
    noise levels (std of noise in a,b). If *noise* is a two
    element tuple or list, the first and second elements specify
    the noise levels of a and b, respectively.
    default: noise=(0,0)
    
    """
    l=[len(a),len(b)]
    cross=cpsd_quasisync
    if l[0]==l[1]:
        cross=cpsd
    elif l[0]>l[1]:
        a,b=b,a
        l=l[::-1]
    step1,nens,nfft=_stepsize(l[0],nfft)
    step2,nens,nfft=_stepsize(l[1],nfft,nens=nens)
    if noise.__class__ not in [list,tuple,np.ndarray]:
        noise=[noise,noise]
    elif len(noise)==1:
        noise=[noise[0],noise[0]]
    if nens<=2:
        raise Exception("Coherence must be computed from a set of ensembles.")
    # fs=1 is ok because it comes out in the normalization.  (noise normalization depends on this)
    out=(cross(a,b,nfft,1,window=window)**2)/((psd(a,nfft,1,window=window,step=step1)-noise[0]**2/np.pi)*(psd(b,nfft,1,window=window,step=step2)-noise[1]**2/np.pi))
    if debias:
        return out*(1+1./nens)-1./nens # This is from Benignus1969, it seems to work (make data with different nens (nfft) agree).
    return out

def cpsd_quasisync(a,b,nfft,fs,window='hann'):
    """
    Compute the cross power spectral density (CPSD) of the signals *a* and *b*.
    
    *a* and *b* do not need to be 'tightly' synchronized, and can even be different
    lengths, but the first- and last-index of both series should be synchronized
    (to whatever degree you want unbiased phases).

    This performs:
    fft(a)*conj(fft(b))
    Note that this is consistent with *np.correlate*'s definition of correlation.
    (The conjugate of D.B. Chelton's definition of correlation.)

    The two signals should be the same length, and should both be real.

    See also:
    psd,cohere,cpsd,numpy.fft

    Parameters
    ----------
    *a*      : The first signal.
    *b*      : The second signal.
    *nfft*   : The number of points in the fft.
    *fs*     : The sample rate (e.g. sample/second).
    *window* : The window to use (default: 'hann'). Valid entries are:
                 None,1               : uses a 'boxcar' or ones window.
                 'hann'               : hanning window.
                 a length(nfft) array : use this as the window directly.

    It detrends the data and uses a minimum of 50% overlap for the shorter of *a* and
    *b*. For the longer, the overlap depends on the difference in size.
    1-(l_short/l_long) data will be underutilized (where l_short and l_long are
    the length of the shorter and longer series, respectively).

    The units of the spectra is the product of the units of *a* and *b*, divided by
    the units of fs.
    """
    if np.iscomplexobj(a) or np.iscomplexobj(b):
        raise Exception
    l=[len(a),len(b)]
    if l[0]==l[1]:
        return cpsd(a,b,nfft,fs,window=window)
    elif l[0]>l[1]:
        a,b=b,a
        l=l[::-1]
    step=[0,0]
    step[0],nens,nfft=_stepsize(l[0],nfft)
    step[1],nens,nfft=_stepsize(l[1],nfft,nens=nens)
    fs=np.float64(fs)
    if window=='hann':
        window=np.hanning(nfft)
    elif window is None or window==1:
        window=np.ones(nfft)
    fft_inds=slice(1,np.floor(nfft/2.+1))
    wght=2./(window**2).sum()
    pwr=fft(detrend(a[0:nfft])*window)[fft_inds]*np.conj(fft(detrend(b[0:nfft])*window)[fft_inds])
    if nens-1:
        for i1,i2 in zip(range(step[0],l[0]-nfft,step[0]),range(step[1],l[1]-nfft,step[1])):
            pwr+=fft(detrend(a[i1:(i1+nfft)])*window)[fft_inds]*np.conj(fft(detrend(b[i2:(i2+nfft)])*window)[fft_inds])
    pwr*=wght/nens/fs
    return np.abs(pwr)
    

def cpsd(a,b,nfft,fs,window='hann',step=None):
    """
    Compute the cross power spectral density (CPSD) of the signals *a* and *b*.

    This performs:
    fft(a)*conj(fft(b))
    Note that this is consistent with *np.correlate*'s definition of correlation.
    (The conjugate of D.B. Chelton's definition of correlation.)

    The two signals should be the same length, and should both be real.

    See also:
    psd,cohere,numpy.fft

    Parameters
    ----------
    *a*      : The first signal.
    *b*      : The second signal.
    *nfft*   : The number of points in the fft.
    *fs*     : The sample rate (e.g. sample/second).
    *window* : The window to use (default: 'hann'). Valid entries are:
                 None,1               : uses a 'boxcar' or ones window.
                 'hann'               : hanning window.
                 a length(nfft) array : use this as the window directly.
    *step*   : Use this to specify the overlap.  For example:
               step=nfft/2 specifies a 50% overlap.
               step=nfft specifies no overlap.
               step=2*nfft means that half the data will be skipped.
               By default, *step* is calculated to maximize data use and have
               at least 50% overlap.

    cpsd removes a linear trend from the data

    For computing cpsd's of variables of different size, use cpsd_quasisync.

    The units of the spectra is the product of the units of *a* and *b*, divided by the units of fs.
    """
    if np.iscomplexobj(a) or np.iscomplexobj(b):
        raise Exception
    auto_psd=False
    if a is b:
        auto_psd=True
    l=len(a)
    step,nens,nfft=_stepsize(l,nfft,step=step)
    fs=np.float64(fs)
    if window.__class__ is str and window.startswith('hann'):
        window=np.hanning(nfft)
    elif window is None or window==1:
        window=np.ones(nfft)
    fft_inds=slice(1,int(nfft/2.+1))
    wght=2./(window**2).sum()
    s1=fft(detrend(a[0:nfft])*window)[fft_inds]
    if auto_psd:
        pwr=np.abs(s1)**2
    else:
        pwr=s1*np.conj(fft(detrend(b[0:nfft])*window)[fft_inds])
    if nens-1:
        for i in range(step,l-nfft+1,step):
            print (i)
            s1=fft(detrend(a[i:(i+nfft)])*window)[fft_inds]
            if auto_psd:
                pwr+=np.abs(s1)**2
            else:
                pwr+=s1*np.conj(fft(detrend(b[i:(i+nfft)])*window)[fft_inds])
    pwr*=wght/nens/fs
    #print 1,step,nens,l,nfft,wght,fs
    #error
    if auto_psd:# No need to take the abs again.
        return pwr
    return np.abs(pwr)

def psd(a,nfft,fs,window='hann',step=None):
    """
    Compute the power spectral density (PSD).
    
    This function computes the one-dimensional *n*-point PSD.

    The units of the spectra is the product of the units of *a* and *b*, divided by the units of fs.


    Parameters
    ----------
    *a*      : 1d-array_like, the signal. Currently only supports vectors.
    *nfft*   : The number of points in the fft.
    *fs*     : The sample rate (e.g. sample/second).
    *window* : The window to use (default: 'hann'). Valid entries are:
                 None,1               : uses a 'boxcar' or ones window.
                 'hann'               : hanning window.
                 a length(nfft) array : use this as the window directly.
    *step*   : Use this to specify the overlap.  For example:
               step=nfft/2 specifies a 50% overlap.
               step=nfft specifies no overlap.
               step=2*nfft means that half the data will be skipped.
               By default, *step* is calculated to maximize data use and have
               at least 50% overlap.
             
    Returns
    -------
    pow    : 1d-array
    
    --credit: This was copied from JN's fast_psd.m routine. --

    See also:
    numpy.fft
    
    """
    return cpsd(a,a,nfft,fs,window=window,step=step)
