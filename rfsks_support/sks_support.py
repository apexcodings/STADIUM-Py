import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# plt.style.use('ggplot')
plt.style.use('seaborn')
import matplotlib.gridspec as gridspec
import tqdm
import os, glob
from rf import read_rf, IterMultipleComponents
from obspy import UTCDateTime as UTC
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
from obspy.core import read
from obspy.taup import TauPyModel
from rfsks_support.rfsks_extras import plot_trigger, plot_trace, plot_SKS_measure
from obspy.signal.trigger import recursive_sta_lta,classic_sta_lta,z_detect,carl_sta_trig,delayed_sta_lta, trigger_onset
import splitwavepy as sw
import logging
import math
from mpl_toolkits.basemap import Basemap
from rfsks_support.plotting_libs import plot_topo, plot_merc

def plot_point_on_basemap(map, point, angle, length):
    '''
    point - Tuple (x, y)
    angle - Angle in degrees.
    length - Length of the line to plot.
    '''

    # unpack the point
    x, y = point

    # find the start and end point
    halfleny = length/2 * math.sin(math.radians(float(angle)))
    halflenx = length/2 * math.cos(math.radians(float(angle)))

    endx,endy = map(x+halflenx,y+halfleny)
    startx,starty = map(x-halflenx,y-halfleny)
    map.plot([startx,endx],[starty,endy],color='k',zorder=3)

from cmath import rect, phase
from math import radians, degrees
def mean_angle(deg):
    return degrees(phase(sum(rect(1, radians(d)) for d in deg)/len(deg)))


## Fine tuning of SKS
advinputSKS = "Settings/advSKSparam.txt"
inpSKS = pd.read_csv(advinputSKS,sep="|",index_col ='PARAMETERS')

class sks_measurements:

    def __init__(self,plot_measure_loc=None):
        self.logger = logging.getLogger(__name__)
        self.plot_measure_loc= plot_measure_loc
        print(self.plot_measure_loc)
        # pass

    ## Pre-processing
    def SKScalc(self, dataSKSfileloc,trace_loc_ENZ=None,trace_loc_RTZ=None,trigger_loc=None,method = 'None'):
        
        self.logger.info("Cut the traces around the SKS arrival")
        sksfiles = glob.glob(dataSKSfileloc+f"*-{str(inpSKS.loc['data_sks_suffix','VALUES'])}.h5")
        self.logger.info(sksfiles)
        count=0
        meas_file = self.plot_measure_loc+'done_measurements.txt'
        if not os.path.exists(meas_file):
            f = open(meas_file, 'w')
            finished_events = np.array([])
            finished_file = np.array([])
        elif os.path.exists(meas_file):
            f = open(meas_file, 'a')
            finished_measure_df = pd.read_csv(meas_file,header=None,names=['filename','event_name'])
            finished_file = finished_measure_df['filename'].tolist()
            finished_events = finished_measure_df['event_name'].tolist()
            # print(finished_events)
        
        # measurement_list=[]
        for i,sksfile in enumerate(sksfiles):
            print(f'file = ',sksfile)
            data = read_rf(sksfile, 'H5')
            self.logger.info(f"Calculating SKS arrival times for {sksfile}\n")
            net_name = os.path.basename(sksfile).split("-")[0]
            stn_name = os.path.basename(sksfile).split("-")[1]
            # print("file name",net_name+stn_name)
            sks_meas_file = open(self.plot_measure_loc+f"{net_name}_{stn_name}_{str(inpSKS.loc['sks_meas_indiv','VALUES'])}",'w')
            sks_meas_file.write("Stlon Stlat Stbaz\n")
            sks_meas_file.write("{:.4f} {:.4f} {:.4f}\n".format(data[0].stats.station_longitude,data[0].stats.station_latitude,data[0].stats.back_azimuth))
            sks_meas_file.write("EventTime EvLong EvLat FastDirection(degs) deltaFastDir(degs) LagTime(s) deltaLagTime(s)\n")
            
            for stream3c in IterMultipleComponents(data, 'onset', 3):
                count+=1
                if sksfile in finished_file and str(stream3c[0].stats.event_time) in finished_events:
                    # print("Done Measurents")
                    continue
                else:
                    print(f"{sksfile} and {stream3c[0].stats.event_time} not done")
                    f.write("{},{}\n".format(sksfile,stream3c[0].stats.event_time))
                # self.logger.info(f"Working on {count}/{int(len(data)/3)}: {stream3c[0].stats.event_time}")

                ## check if the length of all three traces are equal
                len_tr_list=list()
                for tr in stream3c:
                    len_tr_list.append(len(tr))
                if len(set(len_tr_list))!=1:
                    self.logger.warning(f"{count}/{int(len(data)/3)} Bad trace: {stream3c[0].stats.event_time}")
                    continue

                ## filter the trace
                st = stream3c.filter('bandpass', freqmin=float(inpSKS.loc['minfreq','VALUES']), freqmax=float(inpSKS.loc['maxfreq','VALUES']))
                st.detrend('linear')
                # st.taper(max_percentage=0.05, type="hann")
                sps = st[0].stats.sampling_rate
                t = st[0].stats.starttime
                ## trim the trace
                # ev_sttime = st[0].stats.starttime
                # ev_endtime = st[0].stats.endtime
                trace1 = st.trim(t+int(inpSKS.loc['trimstart','VALUES']), t+int(inpSKS.loc['trimend','VALUES']))



                ## plot the ENZ
                if trace_loc_ENZ:
                    plot_trace(trace1,trace_loc_ENZ)
                
                ## Rotate to RTZ
                ## trace2[0]->BHT; trace2[1]->BHR; trace2[2]->BHZ;
                trace1.rotate('NE->RT')
#                snr_rt = sw.core.snrRH(trace1[1].data,trace1[0].data)
#                if snr_rt>3:
#                    pass
#                else:
#                    continue

                
                plt_id = f"{trace1[0].stats.network}-{trace1[0].stats.station}"
                evyear = trace1[0].stats.event_time.year
                evmonth = trace1[0].stats.event_time.month
                evday = trace1[0].stats.event_time.day
                evhour = trace1[0].stats.event_time.hour
                evminute = trace1[0].stats.event_time.minute
                
                # ## plot all three traces RTZ
                if trace_loc_RTZ:
                    plot_trace(trace1,trace_loc_RTZ)

                ######################
                #  Different picker methods. User's choice?
                ######################
                # method = 'None'
                ### operating on transverse component
                if method=="recursive_sta_lta":
                    # self.logger.info(f"Method is {method}")
                    cft = recursive_sta_lta(trace1[1].data, int(1 * sps), int(5 * sps))
                    threshold = (float(inpSKS.loc['sks_picking_algo_thr0','VALUES']), float(inpSKS.loc['sks_picking_algo_thr1','VALUES']))#(2.5,0.65)
                    on_off = np.array(trigger_onset(cft, threshold[0], threshold[1]))
                    
                    if trigger_loc and on_off.shape[0]==1:
                        outfile = trigger_loc+f'{plt_id}-{trace1[0].stats.event_time}-trigger.png'
                        plot_trigger(trace1[1], cft, on_off, threshold[0], threshold[1], outfile=outfile)
                    

                elif method=="classic_sta_lta":
                    cft = classic_sta_lta(trace1[1].data, int(5 * sps), int(10 * sps))
                    threshold = (float(inpSKS.loc['sks_picking_algo_thr0','VALUES']), float(inpSKS.loc['sks_picking_algo_thr1','VALUES']))#(1.5, 0.5)
                    on_off = np.array(trigger_onset(cft, threshold[0], threshold[1]))
                elif method=="z_detect":
                    cft = z_detect(trace1[1].data, int(10 * sps))
                    threshold = (float(inpSKS.loc['sks_picking_algo_thr0','VALUES']), float(inpSKS.loc['sks_picking_algo_thr1','VALUES']))#(-0.4, -0.3)
                    on_off = np.array(trigger_onset(cft, threshold[0], threshold[1]))
                elif method=="carl_sta_trig":
                    cft = carl_sta_trig(trace1[1].data, int(5 * sps), int(10 * sps), 0.8, 0.8)
                    threshold = (float(inpSKS.loc['sks_picking_algo_thr0','VALUES']), float(inpSKS.loc['sks_picking_algo_thr1','VALUES']))#(20.0, -20.0)
                    on_off = np.array(trigger_onset(cft, threshold[0], threshold[1]))
                elif method=="delayed_sta_lta":
                    cft = delayed_sta_lta(trace1[1].data, int(5 * sps), int(10 * sps))
                    threshold = (float(inpSKS.loc['sks_picking_algo_thr0','VALUES']), float(inpSKS.loc['sks_picking_algo_thr1','VALUES']))#(5, 10)
                    on_off = np.array(trigger_onset(cft, threshold[0], threshold[1]))
                else:
                    self.logger.info("No valid method specified")
                    pass

                if on_off.shape[0]==1:
                    trace1.rotate('RT->NE')
                    trace2 = trace1
                    # self.logger.info(f"Measure splitting for {plt_id}-{trace1[0].stats.event_time}: {trace2[1].stats.channel},{trace2[0].stats.channel}")
                    realdata = sw.Pair(trace2[1].data,trace2[0].data, delta=1/sps) #creates Pair from two traces, delta: sample interval
                    try:
                        measure = sw.EigenM(realdata, lags=(float(inpSKS.loc['minlag','VALUES']), float(inpSKS.loc['maxlag','VALUES']), 40))
                        
                    except Exception as e:
                        self.logger.error(e)
                        continue
                    d = measure.srcpoldata_corr().chop()
                    snr = sw.core.snrRH(d.x,d.y) #Restivo and Helffrich (1999) signal to noise ratio
                    # and lam1_lam2 < float(inpSKS.loc['lam12_ratio','VALUES'])
                    squashfast = np.sum(measure.lam1/measure.lam2, axis=0)
                    squashlag = np.sum(measure.lam1/measure.lam2, axis=1)
                    if measure.dfast < int(inpSKS.loc['maxdfast','VALUES']) and measure.dlag < float(inpSKS.loc['maxdlag','VALUES']) and snr > float(inpSKS.loc['snratio','VALUES']):
                        '''
                        Uses the one sigma error in fast direction and lag time. Calculated by taking a quarter of the width of 95% confidence region (found using F-test) of lambda2.
                        '''
                        # lam1_lam2 = float(measure.lam1/measure.lam2)
                        # print(float(measure.lam1/measure.lam2))
                        sks_meas_file.write("{} {:8.4f} {:8.4f} {:6.1f} {:6.1f} {:.1f} {:.1f}\n".format(trace1[0].stats.event_time,trace1[0].stats.event_longitude,trace1[0].stats.event_latitude,measure.fast,measure.dfast,measure.lag,measure.dlag))
                        if self.plot_measure_loc:
                            plot_SKS_measure(measure)
                            plt.savefig(self.plot_measure_loc+f'{plt_id}-{evyear}_{evmonth}_{evday}_{evhour}_{evminute}.png')
                            plt.close('all')  
                            self.logger.info(f"{count}/{int(len(data)/3)} Stored: {trace1[0].stats.event_time}; dfast = {measure.dfast}, dlag = {measure.dlag}")

                        if int(inpSKS.loc['error_plot','VALUES']):
                            plt.close('all')
                            fig,ax = plt.subplots(2,2)
                            ax[0,0].plot(measure.degs[0,:],measure.fastprofile(),'b')
                            ax[0,0].axvline(measure.fast,color='r')
                            ax[0,0].axvline(measure.fast-2*measure.dfast,alpha=0.5,color='r')
                            ax[0,0].axvline(measure.fast+2*measure.dfast,alpha=0.5,color='r')
                            ax[0,0].set_title('fast direction')

                            ax[0,1].plot(measure.lags[:,0],measure.lagprofile(),'b')
                            ax[0,1].axvline(measure.lag,color='r')
                            ax[0,1].axvline(measure.lag-2*measure.dlag,alpha=0.5,color='r')
                            ax[0,1].axvline(measure.lag+2*measure.dlag,alpha=0.5,color='r')
                            ax[0,1].set_title('lag time')

                            ax[1,0].plot(measure.degs[0,:],squashfast)
                            ax[1,0].axvline(x=measure.degs[0,np.argmax(squashfast)],color='r')
                            ax[1,0].set_title(f'L1/L2 Fast: {measure.degs[0,np.argmax(squashfast)]}')
                            ax[1,1].plot(measure.lags[:,0],squashlag)
                            ax[1,1].axvline(x=measure.degs[0,np.argmax(squashlag)],color='r')
                            ax[1,1].set_title(f'L1/L2 Lag: {measure.degs[0,np.argmax(squashlag)]}')
                            plt.savefig(self.plot_measure_loc+f'errorplot_{plt_id}-{evyear}_{evmonth}_{evday}_{evhour}_{evminute}.png')

                    else:
                        self.logger.warning("{}/{} Rejected: {}! dfast = {:.1f}, dlag = {:.1f}, snr: {:.1f}".format(count,int(len(data)/3),stream3c[0].stats.event_time,measure.dfast,measure.dlag,snr))#; Consider changing the trim window
                else:
                    self.logger.info(f"{count}/{int(len(data)/3)} Bad phase pick: {stream3c[0].stats.event_time}")

            sks_meas_file.close()
        f.close()


    ## plotting the measurement
    def plot_sks_map(self,sks_stations_infofile):
#        print('inside ',self.plot_measure_loc)
            

        all_sks_files = glob.glob(self.plot_measure_loc+f"*_{str(inpSKS.loc['sks_meas_indiv','VALUES'])}")
        station_data_all = pd.DataFrame(columns=['NET','STA','lon','lat','AvgFastDir','AvgLagTime','NumMeasurements'])
        station_data_zero = pd.DataFrame(columns=['NET','STA','lon','lat','AvgFastDir','AvgLagTime','NumMeasurements'])
        station_data_one = pd.DataFrame(columns=['NET','STA','lon','lat','AvgFastDir','AvgLagTime','NumMeasurements'])
        station_data_four = pd.DataFrame(columns=['NET','STA','lon','lat','AvgFastDir','AvgLagTime','NumMeasurements'])
        station_data_five = pd.DataFrame(columns=['NET','STA','lon','lat','AvgFastDir','AvgLagTime','NumMeasurements'])
        for i,sksfile in enumerate(all_sks_files):
            sksfilesplit = sksfile.split("/")[-1].split(".")[0].split("-")[0:2]
            net_sta = "_".join(sksfilesplit)
            figure_name = self.plot_measure_loc+f"../{net_sta}_{str(inpSKS.loc['sks_measure_map','VALUES'])}.png"
            if not os.path.exists(figure_name):
                if sum(1 for line in open(sksfile)) == 3:
                    stn_info = pd.read_csv(sksfile, nrows=1,delimiter='\s+')
                    # print('sksfile:',sksfile)
                    net_net = sksfile.split("/")[-1].split("_")[0]
                    sta_sta = sksfile.split("/")[-1].split("_")[1]
                    # print('sksfile:',net_net,sta_sta)
                    # print(f'',net_net,sta_sta, round(stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),'0.001','0.1','0')
                    station_data_all.loc[i] = [net_net,sta_sta, round(stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),'0.001','0.0','0']
                    station_data_zero.loc[i] = [net_net,sta_sta, round(stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),'0.001','0.0','0']

                elif sum(1 for line in open(sksfile)) > 3 and sum(1 for line in open(sksfile)) <= 7:
                    stn_info = pd.read_csv(sksfile, nrows=1,delimiter='\s+')
                    sksdata = pd.read_csv(sksfile,skiprows=2,delimiter='\s+')
                    # print('sksfile:',sksfile)
                    net_net = sksfile.split("/")[-1].split("_")[0]
                    sta_sta = sksfile.split("/")[-1].split("_")[1]
                    # print('sksfile:',net_net,sta_sta)
                    #net_sta = f"{sksfile.split("_")["/"][-1].split("_")[0]}_{sksfile.split("_")[1]}"
                    newfastdir=[]
                    for val in sksdata['FastDirection(degs)']:
                        if val<-45 and val>-91:
                            newfastdir.append(val+180)
                        else:
                            newfastdir.append(val)

                    sksdata['FastDirection(degs)'] = np.array(newfastdir)
                    # print(sksdata['FastDirection(degs)'])
                    station_data_all.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]
                    station_data_one.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]


                elif sum(1 for line in open(sksfile)) > 7 and sum(1 for line in open(sksfile)) <= 14:
                    stn_info = pd.read_csv(sksfile, nrows=1,delimiter='\s+')
                    sksdata = pd.read_csv(sksfile,skiprows=2,delimiter='\s+')
                    # print('sksfile:',sksfile)
                    net_net = sksfile.split("/")[-1].split("_")[0]
                    sta_sta = sksfile.split("/")[-1].split("_")[1]
                    # print('sksfile:',net_net,sta_sta)
                    #net_sta = f"{sksfile.split("_")["/"][-1].split("_")[0]}_{sksfile.split("_")[1]}"
                    newfastdir=[]
                    for val in sksdata['FastDirection(degs)']:
                        if val<-45 and val>-91:
                            newfastdir.append(val+180)
                        else:
                            newfastdir.append(val)

                    sksdata['FastDirection(degs)'] = np.array(newfastdir)
                    # print(sksdata['FastDirection(degs)'])
                    station_data_all.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]
                    station_data_four.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]


                elif sum(1 for line in open(sksfile)) > 15:
                    stn_info = pd.read_csv(sksfile, nrows=1,delimiter='\s+')
                    sksdata = pd.read_csv(sksfile,skiprows=2,delimiter='\s+')
                    # print('sksfile:',sksfile)
                    net_net = sksfile.split("/")[-1].split("_")[0]
                    sta_sta = sksfile.split("/")[-1].split("_")[1]
                    # print('sksfile:',net_net,sta_sta)
                    #net_sta = f"{sksfile.split("_")["/"][-1].split("_")[0]}_{sksfile.split("_")[1]}"
                    newfastdir=[]
                    for val in sksdata['FastDirection(degs)']:
                        if val<-45 and val>-91:
                            newfastdir.append(val+180)
                        else:
                            newfastdir.append(val)

                    sksdata['FastDirection(degs)'] = np.array(newfastdir)
                    # print(sksdata['FastDirection(degs)'])
                    station_data_all.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]
                    station_data_five.loc[i] = [net_net,sta_sta,round( stn_info['Stlon'].values[0],4),round(stn_info['Stlat'].values[0],4),round(mean_angle(sksdata['FastDirection(degs)']),3),sksdata['LagTime(s)'].mean(),sksdata.shape[0]]


                # print(station_data_all.head())
                station_data_all['NumMeasurements'] = np.array([int(val) for val in station_data_all['NumMeasurements']])
                station_data_all.to_csv(self.plot_measure_loc+"../all_sks_measure.txt",index=None, header=True,sep=' ', float_format='%.4f')
                # print(self.plot_measure_loc+"../all_sks_measure.txt")
                station_data_zero['NumMeasurements'] = np.array([int(val) for val in station_data_zero['NumMeasurements']])
                station_data_zero.to_csv(self.plot_measure_loc+"../0_sks_measure.txt",index=None, header=True,sep=' ', float_format='%.4f')
                # print(self.plot_measure_loc+"../0_sks_measure.txt")
                station_data_one['NumMeasurements'] = np.array([int(val) for val in station_data_one['NumMeasurements']])
                station_data_one.to_csv(self.plot_measure_loc+"../1_sks_measure.txt",index=None, header=True,sep=' ', float_format='%.4f')
                # print(self.plot_measure_loc+"../1_sks_measure.txt")
                station_data_four['NumMeasurements'] = np.array([int(val) for val in station_data_four['NumMeasurements']])
                station_data_four.to_csv(self.plot_measure_loc+"../4_sks_measure.txt",index=None, header=True,sep=' ', float_format='%.4f')
                # print(self.plot_measure_loc+"../4_sks_measure.txt")
                station_data_five['NumMeasurements'] = np.array([int(val) for val in station_data_five['NumMeasurements']])
                station_data_five.to_csv(self.plot_measure_loc+"../5_sks_measure.txt",index=None, header=True,sep=' ', float_format='%.4f')
                # print(self.plot_measure_loc+"../5_sks_measure.txt")

                
                if np.abs(station_data_all['lon'].max()-station_data_all['lon'].min())<10 or np.abs(station_data_all['lat'].max()-station_data_all['lat'].min())<2:
                    lblon = station_data_all['lon'].min() - 2
                    lblat = station_data_all['lat'].min() - 2

                    ublon = station_data_all['lon'].max() + 2
                    ublat = station_data_all['lat'].max() + 2
                else:
                    lblon = station_data_all['lon'].min() - 0.5
                    lblat = station_data_all['lat'].min() - 0.5

                    ublon = station_data_all['lon'].max() + 0.5
                    ublat = station_data_all['lat'].max() + 0.5

                ## Visualize
                fig = plt.figure(figsize=(10,10))
                ax = fig.add_subplot(111)
                map = Basemap(projection='merc',resolution = 'h', area_thresh = 1000., llcrnrlon=lblon, llcrnrlat=lblat,urcrnrlon=ublon, urcrnrlat=ublat, epsg=4839)
                map.drawmapboundary(color='k', linewidth=2, zorder=1)
                map.arcgisimage(service='World_Physical_Map', xpixels = 5000, verbose= True, dpi=300)

                map.etopo(scale=2.5, alpha=0.5, zorder=2) # decrease scale (0-1) to downsample the etopo resolution
                #The image has a 1" arc resolution
                #map.shadedrelief(scale=1, zorder=1)
                map.drawcoastlines(color='k',linewidth=0.5)
                # map.fillcontinents()
                map.drawcountries(color='k',linewidth=0.5)
                map.drawstates(color='gray',linewidth=0.05)
                map.drawrivers(color='blue',linewidth=0.05)
                
                map.drawparallels(np.linspace(lblat,ublat,5,dtype='int16').tolist(),labels=[1,0,0,0],linewidth=0)
                map.drawmeridians(np.linspace(lblon,ublon,5,dtype='int16').tolist(),labels=[0,0,0,1],linewidth=0)
        #        stlons,stlats = map(station_data_all['lon'].values,station_data_all['lat'].values)
                stlon0s,stlat0s = map(station_data_zero['lon'].values,station_data_zero['lat'].values)
                stlon1s,stlat1s = map(station_data_one['lon'].values,station_data_one['lat'].values)
                stlon4s,stlat4s = map(station_data_four['lon'].values,station_data_four['lat'].values)
                stlon5s,stlat5s = map(station_data_five['lon'].values,station_data_five['lat'].values)
        #        print('test = ',stlons, stlats,station_data_all['AvgLagTime'])
        #        map.scatter(stlons, stlats, c='b', marker='o', s=60*station_data_all['AvgLagTime'],edgecolors='k',linewidths=0.1, zorder=4)
                map.scatter(stlon0s, stlat0s, c='lightgray', marker='o', s=60, edgecolors='k',linewidths=0.3, zorder=2)
                map.scatter(stlon1s, stlat1s, c='cornflowerblue', marker='o', s=60*station_data_one['AvgLagTime'],edgecolors='k',linewidths=0.1, zorder=4)
                map.scatter(stlon4s, stlat4s, c='navy', marker='o', s=60*station_data_four['AvgLagTime'],edgecolors='k',linewidths=0.1, zorder=4)
                map.scatter(stlon5s, stlat5s, c='black', marker='o', s=60*station_data_four['AvgLagTime'],edgecolors='k',linewidths=0.1, zorder=4)


                legendarray = []
                for a in [1, 2, 3]:
                    legendarray.append(map.scatter([], [], c='b', alpha=0.6, s=60*a,label=f"{a}s",edgecolors='k'))
                
                legendarray.append(map.scatter([], [], c='r', alpha=0.99, s=60, edgecolors='k'))
                legendarray.append(map.scatter([], [], c='cornflowerblue', alpha=0.99, s=60, edgecolors='k'))
                legendarray.append(map.scatter([], [], c='navy', alpha=0.99, s=60, edgecolors='k'))
                legendarray.append(map.scatter([], [], c='black', alpha=0.99, s=60, edgecolors='k'))
                legendarray.append(map.scatter([], [], c='gold', marker='^', alpha=0.99, s=60, edgecolors='k'))
                legendarray.append(map.scatter([], [], c='red', marker='^', alpha=0.99, s=60, edgecolors='k'))

                


                for jj in range(station_data_one.shape[0]):
                    plot_point_on_basemap(map, point=(station_data_one['lon'].values[jj],station_data_one['lat'].values[jj]), angle = station_data_one['AvgFastDir'].values[jj], length = 1.5)

                for jj in range(station_data_four.shape[0]):
                    plot_point_on_basemap(map, point=(station_data_four['lon'].values[jj],station_data_four['lat'].values[jj]), angle = station_data_four['AvgFastDir'].values[jj], length = 1.5)

                for jj in range(station_data_five.shape[0]):
                    plot_point_on_basemap(map, point=(station_data_five['lon'].values[jj],station_data_five['lat'].values[jj]), angle = station_data_five['AvgFastDir'].values[jj], length = 1.5)

                # plt.tight_layout()
                
                #draw mapscale
                msclon,msclat = ublon-4,lblat+1.0
                msclon0,msclat0 = station_data_all['lon'].mean(),station_data_all['lat'].mean()
                map.drawmapscale(msclon,msclat,msclon0,msclat0, 250, barstyle='fancy', zorder=6)

                leg1 = plt.legend([legendarray[3],legendarray[4],legendarray[5],legendarray[6]],['No measurement','1-3 measurements','4-14 measurements','15+ measurements'],frameon=False, loc='upper left',labelspacing=1,handletextpad=0.1)
                leg2 = plt.legend(frameon=False, loc='upper right',labelspacing=1,handletextpad=0.1)
                ax.add_artist(leg1)

                plt.savefig(self.plot_measure_loc+'../SKS_Map.png',bbox_inches='tight',dpi=300)
                self.logger.info(f"SKS measurement figure: {self.plot_measure_loc+'../SKS_Map.png'}")

        ######### Station map  ###############
                # plot all stations    
                df = pd.read_csv(sks_stations_infofile,delimiter='|')
                stations = df['Station'].values
                laat = df['Latitude'].values
                loon = df['Longitude'].values


                fig = plt.figure(figsize=(10,10))
                ax = fig.add_subplot(111)
                map = Basemap(projection='merc',resolution = 'h', area_thresh = 1000., llcrnrlon=lblon, llcrnrlat=lblat,urcrnrlon=ublon, urcrnrlat=ublat, epsg=4839)
                map.drawmapboundary(color='k', linewidth=2, zorder=1)
                map.arcgisimage(service='World_Physical_Map', xpixels = 5000, verbose= True, dpi=300)

                map.etopo(scale=2.5, alpha=0.5, zorder=2) # decrease scale (0-1) to downsample the etopo resolution
                #The image has a 1" arc resolution
                #map.shadedrelief(scale=1, zorder=1)
                map.drawcoastlines(color='k',linewidth=0.5)
                # map.fillcontinents()
                map.drawcountries(color='k',linewidth=0.5)
                map.drawstates(color='gray',linewidth=0.05)
                map.drawrivers(color='blue',linewidth=0.05)
                
                map.drawparallels(np.linspace(lblat,ublat,5,dtype='int16').tolist(),labels=[1,0,0,0],linewidth=0)
                map.drawmeridians(np.linspace(lblon,ublon,5,dtype='int16').tolist(),labels=[0,0,0,1],linewidth=0)


                allstlons,allstlats = map(df['Longitude'].values,df['Latitude'].values)
                map.scatter(allstlons,allstlats , c='gold', marker='^', s=60, facecolors='none', edgecolors='b',linewidths=0.3, zorder=2)
                


                stlons,stlats = map(station_data_all['lon'].values,station_data_all['lat'].values)
        #        print('test = ',stlons, stlats,station_data_all['AvgLagTime'])
        #        map.scatter(stlons, stlats, c='b', marker='o', s=60*station_data_all['AvgLagTime'],edgecolors='k',linewidths=0.1, zorder=4)
                map.scatter(stlons, stlats, c='red', marker='^', s=60, edgecolors='k',linewidths=0.3, zorder=2)


                #draw mapscale
                msclon,msclat = ublon-4,lblat+2.0
                msclon0,msclat0 = station_data_all['lon'].mean(),station_data_all['lat'].mean()
                map.drawmapscale(msclon,msclat,msclon0,msclat0, 250, barstyle='fancy', zorder=6)
                leg2 = plt.legend([legendarray[7],legendarray[8]],['No data','With data'],frameon=False, loc='upper right',labelspacing=1,handletextpad=0.1)
                ax.add_artist(leg2)

                leg2 = plt.legend(frameon=False, loc='upper right',labelspacing=1,handletextpad=0.1)
                ax.add_artist(leg2)

                plt.savefig(figure_name,bbox_inches='tight',dpi=300)
                self.logger.info(f"SKS measurement figure: {figure_name}")
