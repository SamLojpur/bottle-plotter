# -*- coding: utf-8 -*-
"""
Created on Mon Aug 17 13:48:58 2015

@author: bcolsen
"""
from __future__ import division, print_function
import numpy as np
import pylab as plt
from .kde import kde
from scipy import stats
import sys
from io import BytesIO
import tempfile

#from gradient_bar import gbar

class ash:
    def __init__(self, data, bin_num=None, shift_num=50, normed=True, force_scott = False, rule = 'scott'):
        self.data_min = min(data)
        self.data_max = max(data)
        self.shift_num = shift_num
        self.data = data
        self.data_len = len(self.data)
        self.normed=normed
        ##If None use KDE to autobin
        
        if bin_num == None:
            kde_result = kde(self.data)
            if len(self.data) >= 50 and not force_scott and kde_result:
                self.bw,self.kde_mesh,self.kde_den = kde_result
                self.bins_from_bw()
                self.bw2,self.kde_mesh,self.kde_den = kde(self.data, None, self.ash_mesh.min(), self.ash_mesh.max())
            elif rule=='fd':
                #print("Using FD rule")
                kernel = stats.gaussian_kde(self.data)
                self.bin_width = 2*(stats.iqr(self.data)/(len(self.data)**(1/3)))
                self.bw_from_bin_width()
                kernel.set_bandwidth(self.bw)
                self.bins_from_bw()
                self.kde_mesh = self.ash_mesh
                self.kde_den = kernel(self.kde_mesh)
            else:
                #print("Using Scott's rule")
                kernel = stats.gaussian_kde(self.data)
                kernel.set_bandwidth(rule)
                self.bw = kernel.factor * self.data.std() # kde factor is bandwidth scaled by sigma
                self.bins_from_bw()
                self.kde_mesh = self.ash_mesh
                self.kde_den = kernel(self.kde_mesh)
        else:
            #print("Using bin number: ", bin_num)
            self.set_bins(bin_num)

            kernel = stats.gaussian_kde(self.data)
            kernel.set_bandwidth(self.bw)
            self.kde_mesh = self.ash_mesh
            self.kde_den = kernel(self.kde_mesh)
                
                #self.kde_mesh,self.kde_den
        
        ## KDE on same range as ASH
                    
    def set_bins(self,bin_num):
        self.bin_num = bin_num
        self.bin_width = (self.data_max-self.data_min)/self.bin_num
        self.MIN = self.data_min - self.bin_width
        self.MAX = self.data_max + self.bin_width
        self.SHIFT = self.bin_width/self.shift_num
        
        self.bw_from_bin_width()
        self.calc_ash_den(self.normed)
        self.calc_ash_unc()
    
    def bins_from_bw(self):
        self.bin_width = self.bw * np.sqrt(2*np.pi) #bin with full width half max of band width
        self.bin_num = int(np.ceil(((self.data_max - self.data_min)/self.bin_width)))
        self.MIN = self.data_min - self.bin_width
        self.MAX = self.data_min + self.bin_width*(self.bin_num + 1)
        self.SHIFT = self.bin_width/self.shift_num
        
        self.calc_ash_den(self.normed)
        self.calc_ash_unc()#window at which 68.2% of the area is covered
        
    def bw_from_bin_width(self):
        self.bw = self.bin_width / np.sqrt(2*np.pi)
    
    def calc_ash_den(self, normed=True):
        self.ash_mesh = np.linspace(self.MIN,self.MAX,(self.bin_num+2)*self.shift_num)
        self.ash_den = np.zeros_like(self.ash_mesh)
        for i in range(self.shift_num):
            hist_range = (self.MIN+i*self.SHIFT,self.MAX+i*self.SHIFT- self.bin_width)
            hist, self.bin_edges = np.histogram(self.data,self.bin_num+1,range=hist_range,density=normed)
            #print(self.bin_edges[1]-self.bin_edges[0])
            hist_mesh = np.ravel(np.meshgrid(hist,np.zeros(self.shift_num))[0],order='F')
            self.ash_den = self.ash_den + np.r_[[0]*i,hist_mesh,[0]*(self.shift_num-i)] #pad hist_mesh with zeros and add
            #print(ash_den)
        self.ash_den = self.ash_den/self.shift_num #take the average
        ash_den_index = np.where(self.ash_den > 0)
        self.ash_mesh = self.ash_mesh[ash_den_index]
        self.ash_den = self.ash_den[ash_den_index]
    def calc_ash_unc(self):
        '''window at which 68.2% of the area is covered'''
        tot_area = np.trapz(self.ash_den,self.ash_mesh)
        self.mean = np.average(self.ash_mesh, weights = self.ash_den)
        mean_index = (np.abs(self.ash_mesh-self.mean)).argmin()
        i=1
        area = 0
        self.window = 0
        while area < 0.682:
            window_index = slice(mean_index-i,mean_index+1+i)
            self.window = self.ash_mesh[window_index]
            area = np.trapz(self.ash_den[window_index],self.window)/tot_area
            i+=1
            #print(area)
        self.unc = self.window.max() - self.mean
        self.sigma = np.sqrt(np.average((self.ash_mesh-self.mean)**2, weights=self.ash_den))
        #print(area, self.unc ,self.sigma)
    def plot_ash_infill(self, ax=None, color='#92B2E7', normed=True, alpha=0.75):
        ax = ax if ax else plt.gca()
        fig_tmp = plt.figure(figsize = (6,6))
        # ax = fig_tmp.add_axes([0,0,1,1], facecolor='g', frameon=False)
        # ax.set_xticks([])
        # ax.set_yticks([])
        self.hist_max = 0
        print("SHIFT:", self.SHIFT)
        for i in range(self.shift_num):
            hist_range = (self.MIN+i*self.SHIFT,self.MAX+i*self.SHIFT- self.bin_width)
            self.hist_range = hist_range
            hist, bin_edges = np.histogram(self.data,self.bin_num+1,range=hist_range,density=normed)
            self.hist_max = max(hist) if max(hist) > self.hist_max else self.hist_max
            #gbar(ax, bin_edges[:-1], hist, width=self.bin_width,alpha=0.5/self.shift_num)
            n, bin_edges, patches = ax.hist(self.data,self.bin_num+1,range=hist_range,
                histtype='stepfilled',alpha=alpha/self.shift_num,color = color, linewidth=0,density=normed, rasterized=True)
        ymin, ymax = ax.get_ylim()
        xmin, xmax = ax.get_xlim()
        self.hist_max += self.hist_max*0.1
        ymax = ymax if ymax > self.hist_max else self.hist_max
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(xmin, xmax)
        fig_tmp.canvas.draw()
        with tempfile.NamedTemporaryFile() as fp:
            plt.savefig(fp, transparent=True, type='png')
            self.hist_img = plt.imread(fp.name)
            self.hist_img = self.alpha_over(self.hist_img)
        plt.close(fig_tmp)
        #self.hist_img = np.array(fig_tmp.canvas.renderer._renderer).reshape((480,480,4))
        #outs = BytesIO()
        #plt.savefig(outs, format='png')
        #plt.close(fig_tmp)
        #self.hist_img = plt.imread(outs)
        #print(self.hist_img.shape, file=sys.stderr)
        ax.imshow(self.hist_img, aspect='auto', extent=(xmin, xmax, ymin, ymax ))
        ax.set_ylim(ymin, ymax)
        plt.sca(ax)
        
    def plot_rug(self, ax=None, color='#92B2E7', alpha=0.5, lw=2, ms=20, height = 0.07):
        ax = ax if ax else plt.gca()
        ymin, ymax = ax.get_ylim()
        #print(ymin, ymax)
        y_height = ymax - ymin
        ax.plot(self.data,np.zeros_like(self.data)-y_height*height,'|', alpha=alpha,mew=lw, ms=ms, color=color)
        ax.set_ylim(-ymax*0.15, ymax)
    def plot_stats(self, ax=None, label = None, color='#4C72B0', size = 16, side = 'left', short = True):
        from uncertainties import ufloat
        if side == 'right':
            x,y = (0.96, 0.96)
            ha='right'
        else:
            x,y = (0.04, 0.96)
            ha='left'
        ax = ax if ax else plt.gca()
        mean = ufloat(self.mean,self.sigma)
        label_str = str(label)+' = ' if label else ''
        if short:
            stat_string = label_str+r"$\mathregular{"+"{:.2uSL}".format(mean)+"}$\nN = "+str(self.data_len)
        else:
            stat_string = label_str+r"$\mathregular{"+"{:.2uL}".format(mean)+"}$\nN = "+str(self.data_len)
        ax.text(x, y, stat_string, color=color, ha=ha, va='top', transform=ax.transAxes, size=size)
    def alpha_over(self, img):
        return (img[...,:3]/255)*(img[...,3:]/255)+1-(img[...,3:]/255)
    

if __name__ == "__main__":
    
    import seaborn as sns
    
    mu, sigma = 1000, 10
    data_fake = mu + sigma*np.random.randn(10)
    
    
    bins = None
    scott = False

    data = data_fake

    
    ash_obj = ash(data,bin_num=bins, force_scott=scott)
    
    print(ash_obj.bw, ash_obj.bin_num, ash_obj.bin_width, ash_obj.bin_edges[1]-ash_obj.bin_edges[0])
    
    sns.set_style('ticks',)
    sns.set_context('talk',font_scale=1.5)
    #Plot like this
    fig = plt.figure("ash")
    fig.clf()
    ax = fig.add_subplot(111)
    #plot ASH as a line
    plt.plot(ash_obj.ash_mesh,ash_obj.ash_den)
    
    
    #plt.vlines(ash_obj.mean,0,1)
    #plt.vlines([ash_obj.window.min(),ash_obj.window.max()],0,1)
    
    #plot the solid ASH
    ash_obj.plot_ash_infill()
    
    #barcode like data representation
    ash_obj.plot_rug()
    #plt.vlines(data,-0.03,-0.01,alpha=0.1)
    ash_obj.plot_stats()
    
    
    #plot KDE
    plt.plot(ash_obj.kde_mesh,ash_obj.kde_den)
    
    #for testing auto binning
#    diff_den = ash_obj.ash_den - np.interp(ash_obj.ash_mesh,ash_obj.kde_mesh,ash_obj.kde_den)
#    print(max(abs(diff_den)),ash_obj.bw,ash_obj.bin_num)
#    plt.plot(ash_obj.ash_mesh,diff_den,lw=2)
   
    
    if data is data_fake:
        dist = plt.normpdf(ash_obj.ash_mesh, mu, sigma)
        plt.plot(ash_obj.ash_mesh,dist,'--')
        #plt.plot(ash_obj.ash_mesh,dist-ash_obj.ash_den,'--')
        
    kde_diff = np.interp(ash_obj.ash_mesh, ash_obj.kde_mesh, ash_obj.kde_den) - ash_obj.ash_den
    plt.plot(ash_obj.ash_mesh,kde_diff,'-.')
        
    #ax.spines['right'].set_visible(False)
    #ax.spines['top'].set_visible(False)
    # Only show ticks on the left and bottom spines
    ax.yaxis.set_ticks_position('left')
    ax.xaxis.set_ticks_position('bottom')
    ax.tick_params(direction='in')
    
    #sns.despine(ax=a2,left=True)
    #sns.despine(ax=ax,left=True)
    ax.yaxis.set_ticks([])
    
    plt.tight_layout()
    # plt.show()
    
