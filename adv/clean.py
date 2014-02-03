import tools as tbx
import numpy as np
import warnings

warnings.filterwarnings('ignore',category=np.RankWarning)

def cleanFill(u,bd):
    """
    Clean the array *u* by assigning NaN to the values in *bd* that are True.

    Then fill the gaps by linear interpolation.
    """
    u[bd]=np.NaN
    tbx.fillgaps(u)

def fillpoly(indat,deg,npt):
    """
    Fill gaps in a vector by interpolating using a polynomial.

    *deg* is the degree of the polynomial (see polyfit)

    *npt* is the number of points on either side of the gap
    that the fit occurs over.

    """
    pos=npt
    shft=np.arange(-npt,0)
    im=[]
    ie=[]
    bds=[]
    searching=True
    while pos<len(indat)-npt:
        if searching:
            if np.isnan(indat[pos]):
                ib=pos+shft
                bds+=[pos]
                searching=False
        else:
            if np.isnan(indat[pos]):
                bds+=[pos]
                im+=ie
                ie=[]
            else:
                ie+=[pos]
        if len(ie)==npt:
            searching=True
            inds=np.concatenate((ib,im,ie))
            ie=[]
            im=[]
            #print inds,bds
            fits=np.polyval(np.polyfit(inds,indat[inds],deg),bds)
            for i,f in zip(bds,fits):
                indat[i]=f
            bds=[]
                
        pos+=1
        
            
def spikeThresh(u,thresh):
    """
    Returns a logical vector where a spike of magnitude greater than *thresh* occurs.
    'Negative' and 'positive' spikes are both caught.

    *thresh* must be positive.
    """
    du=np.diff(u)
    bds1=((du[1:]>thresh) & (du[:-1]<-thresh))
    bds2=((du[1:]<-thresh) & (du[:-1]>thresh))
    return np.concatenate(([False],bds1 | bds2,[False]))
    

def rangeLimit(u,range):
    """
    Returns a logical vector that is True where the
    values of *u* are outside of *range*.
    """
    return ~tbx.within(u,range)
    

def calcab(al,Lu_std_u,Lu_std_d2u):
    """
    Solve equations 10 and 11 of Goring+Nikora2002.

    I think they have the equation wrong (power of 2 exponents should be -2,except on sin,cos),
    but I'm not certain, and it doesn't appear to make too much difference.
    """
    #return tuple(np.linalg.solve(np.array([[np.cos(al)**2,np.sin(al)**2],[np.sin(al)**2,np.cos(al)**2]]),np.array([(Lu_std_u)**-2,(Lu_std_d2u)**-2]))**-1) # I think this is correct
    return tuple(np.linalg.solve(np.array([[np.cos(al)**2,np.sin(al)**2],[np.sin(al)**2,np.cos(al)**2]]),np.array([(Lu_std_u)**2,(Lu_std_d2u)**2])))

def phaseSpaceThresh(u):
    """
    Implements the Goring+Nikora2002 despiking method, with Wahl2003 correction.
    """
    if u.ndim==1:
        u=u[:,None]
    u=np.array(u) # Don't want to deal with marray in this function.
    Lu=(2*np.log(u.shape[0]))**0.5
    u=u-u.mean(0)
    du=np.zeros_like(u)
    d2u=np.zeros_like(u)
    du[1:-1]=(u[2:]-u[:-2])/2 # Correct. This is the centered difference.
    #du[1:-1]=np.diff(u,n=2,axis=0) # Wrong: This is the second derivative, not the centered difference.
    d2u[2:-2]=(du[1:-1][2:]-du[1:-1][:-2])/2
    #d2u[2:-2]=np.diff(du[1:-1],n=2,axis=0) # Again, wrong.
    p=(u**2+du**2+d2u**2)
    std_u=np.std(u,axis=0)
    std_du=np.std(du,axis=0)
    std_d2u=np.std(d2u,axis=0)
    alpha=np.arctan2(np.sum(u*d2u,axis=0),np.sum(u**2,axis=0))
    a=np.empty_like(alpha)
    b=np.empty_like(alpha)
    for idx,al in enumerate(alpha):
        #print al,std_u[idx],std_d2u[idx],Lu
        a[idx],b[idx]=calcab(al,Lu*std_u[idx],Lu*std_d2u[idx])
        #print a[idx],b[idx]
    if np.any(np.isnan(a)) or np.any(np.isnan(a[idx])):
        print 'Coefficient calculation error'
    theta=np.arctan2(du,u)
    phi=np.arctan2((du**2+u**2)**0.5,d2u)
    pe=(((np.sin(phi)*np.cos(theta)*np.cos(alpha)+np.cos(phi)*np.sin(alpha))**2)/a+((np.sin(phi)*np.cos(theta)*np.sin(alpha)-np.cos(phi)*np.cos(alpha))**2)/b+((np.sin(phi)*np.sin(theta))**2)/(Lu*std_du)**2)**-1
    pe[:,np.isnan(pe[0,:])]=0
    return (p>pe).flatten('F')
    

def GN2002(u,npt=5000):
    """
    
    """
    bds=np.zeros(len(u),dtype='bool')
    bds[0]=True
    c=0
    ntot=len(u)
    nbins=ntot/npt
    bds_last=np.zeros_like(bds)+np.inf
    while bds.any():
        bds[:nbins*npt]=phaseSpaceThresh(np.array(np.reshape(u[:(nbins*npt)],(npt,nbins),order='F')))
        bds[-npt:]=phaseSpaceThresh(u[-npt:])
        u[bds]=np.NaN
        #tbx.fillgaps(u)
        fillpoly(u,3,12)
        print c,bds.sum()
        #print c,np.nonzero(bds)
        c+=1
        if c>=100:
            error
        if bds.sum()>=bds_last.sum():
            break
        bds_last=bds.copy()
    return bds


## class adv_cleaner(object):
##     """
##     Clean an adv data set, and plot some of the important parameters of this.
##     """
    
##     corr_thresh=70
##     _plot_inds=slice(4000)
##     fill_maxgap=32 # This is 1 second, for 32hz sampling.
    
##     def __init__(self,**kwargs):
##         """
##         Initialize the adv_cleaner object.
##         """
##         for ky,val in kwargs.iteritems():
##             setattr(self,ky,val)
        
    
##     def clean_corr(self,advo,thresh=None):
##         """
##         NaN out the adv velocity (u,v,w) estimates with corr less than *thresh*
        
##         A value of thresh=70% is apparently suggested by Sontek (default).
##           --- I need to see if this works for all datasets.
##         Elgar++2005 suggest using 0.3+0.4*sqrt{s_f/25}.
##         """
##         if thresh is None:
##             thresh=self.corr_thresh
        
##         self.corr_bad=bd=(advo.corr1<thresh)+(advo.corr2<thresh)+(advo.corr3<thresh) # Addition is logical or
##         advo.u[bd]=np.nan
##         advo.v[bd]=np.nan
##         advo.w[bd]=np.nan

##     def fill_vel(self,advo,maxgap=None):
##         """
##         Fill the NaN's in the velocity data.
##         """
##         if maxgap is None:
##             maxgap=self.fill_maxgap
##         fillgaps(advo.u,maxgap)
##         fillgaps(advo.v,maxgap)
##         fillgaps(advo.w,maxgap)

##     def plot_corr(self,advo,**kwargs):
##         """
##         Plot the corr data...
        
##         """
##         if not kwargs.has_key('title'):
##             kwargs['title']='Correlations'
##         self.corr_fig=fg=advo.plot(['corr1','corr2','corr3'],fignum=401,**kwargs)
##         for ax in fg.sax.ax[:,0]:
##             ax.hln(self.corr_thresh,color='r',linestyle='dashed')
##         ax.set_xlim(fg.x_minmax)
        
##     def plot_snr(self,advo):
##         """
##         Plot the SNR data...
##         It is unclear whether SNR should be used for cleaning adv data.  See:
##         www.nortekusa.com/en/knowledge-center/forum/velocimeters/
##         for more info.
##         In particular, see the 'SNR in the Vector' post.
##         """
##         self.snr_fig=fg=advo.plot(['SNR1','SNR2','SNR3'],fignum=402)
##         self.snr_fig.canvas.set_window_title('SNR')
##         self.snr_fig.sax.ax[0,0].set_title('SNR')
        
##     def __call__(self,advo):
##         """
##         Clean the adv data.
##         """
##         self.clean_corr(advo)
##         self.fill_vel(advo)

##     def phase_spacethresh_GN02(self,advo):
##         """
##         The phase-space thresholding method of Goring and Nikora 2002.
##         """
##         du=np.concatenate((np.ones(1)*np.NaN,(advo.u[2:]-advo.u[:-2]),np.ones(1)*np.NaN))/2.
##         d2u=np.concatenate((np.ones(1)*np.NaN,(du[2:]-du[:-2])/2.,np.ones(1)*np.NaN))/2.
        


if __name__=='__main__':

    import adv as avm
    if 'dat' not in vars():
        dat=avm.load('/home/lkilcher/data/ttm_dem_june2012/TTM_Vectors/TTM_NRELvector_Jun2012.h5')
        uorig=dat.u.copy()
        vorig=dat.v.copy()
        worig=dat.w.copy()
        bds=rangeLimit(dat.u,[-2.5,1])# | spikeThresh(dat.u,0.5)
        #bds=rangeLimit(dat.v,[-1.5,1])# | spikeThresh(dat.u,0.5)
        #bds=rangeLimit(dat.w,[-2.5,1])# | spikeThresh(dat.u,0.5)
        dat.u[bds]=np.NaN
        tbx.fillgaps(dat.u)
        rng=slice(610000,5886900)
        newd=dat.subset(rng)
    inds=slice(2150000,2160000,1)
    inds=slice(2151290,2151310,1)

    bds=GK2002(newd.u)
    bds=GK2002(newd.w)

    ## figure(2)
    ## clf()
    ## plot(uorig[inds],'ko')
    ## plot(dat.u[inds])
    ## plot(dat.v[inds])
    ## plot(dat.w[inds])
    ## plot(du[inds])
    ## plot(du[1:][inds])

    inds=slice(None,None,10)
    figure(3)
    clf()
    plot(uorig[rng][inds],'.')
    plot(newd.u[inds],'-')
    plot(worig[rng][inds],'.')
    plot(newd.w[inds],'-')
    #plot(newd.u[inds])
    
    
