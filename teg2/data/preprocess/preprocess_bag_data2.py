"""
The goal here is to take a folder of bag files and bind all data to the
left ZED image timestamps. This involes interpolating the sensor data and
identifiying the correct right image which lags the left by ~5 ms. The
preprocessed data is saved in the bag folder under

    .preprocessed/left_image_bound_to_data.pkl

and

    .preprocessed/preprocessed_data.pkl

which is simply all the original timestamps and sensor readings but no image data.

8 Sept. 2016

3 Nov. 2016
$ rostopic list
/bair_car/GPS2_alt
/bair_car/GPS2_angle
/bair_car/GPS2_day
/bair_car/GPS2_fix
/bair_car/GPS2_hour
/bair_car/GPS2_lat
/bair_car/GPS2_long
/bair_car/GPS2_min
/bair_car/GPS2_mon
/bair_car/GPS2_qual
/bair_car/GPS2_sat
/bair_car/GPS2_sec
/bair_car/GPS2_speed
/bair_car/GPS2_yr
/bair_car/acc
/bair_car/cmd/motor
/bair_car/cmd/steer
/bair_car/encoder
/bair_car/gyro
/bair_car/gyro_heading
/bair_car/motor
/bair_car/state
/bair_car/steer
/bair_car/zed/depth/camera_info
/bair_car/zed/depth/image_rect_color
/bair_car/zed/left/camera_info
/bair_car/zed/left/image_rect_color
/bair_car/zed/right/camera_info
/bair_car/zed/right/image_rect_color
/clock
/rosout
/rosout_agg


















"""

from kzpy3.utils import *
import rospy
import rosbag

############## topics, not necessarily original rosbag names ###################
#
image_topics = ['left_image','right_image']
single_value_topics = ['steer','state','motor','encoder','GPS2_alt','GPS2_angle','GPS2_day','GPS2_fix','GPS2_hour','GPS2_lat','GPS2_long','GPS2_min','GPS2_mon','GPS2_qual','GPS2_sat','GPS2_sec','GPS2_speed','GPS2_yr']
vector3_topics = ['acc','gyro','gyro_heading']
all_topics = image_topics + single_value_topics + vector3_topics
#
######################################################################

############## bagfile data processing to useful forms ##############################
#
A = {} # this will be renamed preprocessed_data for return


def preprocess_bag_data2(bag_folder_path,bagfile_range=[]):
    
    A = {} # this will be renamed preprocessed_data for return

    for topic in all_topics:
        A[topic] = {}

    bag_files = sorted(glob.glob(opj(bag_folder_path,'*.bag')))
    
    if len(bagfile_range) > 0:
        bag_files = bag_files[bagfile_range[0]:(bagfile_range[1]+1)]
    
    print bag_files

    for b in bag_files:
        try:
            print b

            bag = rosbag.Bag(b)

            for topic in single_value_topics:
                for m in bag.read_messages(topics=['/bair_car/'+topic]):
                    t = round(m.timestamp.to_time(),3) # millisecond resolution
                    A[topic][t] = m[1].data

            for topic in vector3_topics:
                if topic != 'gps':
                    for m in bag.read_messages(topics=['/bair_car/'+topic]):
                        t = round(m.timestamp.to_time(),3)
                        A[topic][t] = (m[1].x,m[1].y,m[1].z)

            try:
                topic = 'gps'
                for m in bag.read_messages(topics=['/bair_car/'+topic]):
                    t = round(m.timestamp.to_time(),3)
                    A[topic][t] = (m[1].latitude,m[1].longitude,m[1].altitude)
            except:
                print 'gps problem'

            for m in bag.read_messages(topics=['/bair_car/zed/left/image_rect_color']):
                t = round(m.timestamp.to_time(),3)
                A['left_image'][t] = 'z' # placeholder for ctr

            for m in bag.read_messages(topics=['/bair_car/zed/right/image_rect_color']):
                t = round(m.timestamp.to_time(),3)
                A['right_image'][t] = 'z' # placeholder for ctr
        except Exception as e:
            print e.message, e.args


    for img in ['left_image','right_image']:
        ctr = 0
        sorted_timestamps = sorted(A[img].keys())
        for t in sorted_timestamps:
            A[img][t] = ctr
            ctr += 1
    
    preprocessed_data = A

    left_image_bound_to_data,error_log = _bind_left_image_timestamps_to_data(A)
    print """left_image_bound_to_data,error_log = _bind_left_image_timestamps_to_data(A) """
    timestamps = sorted(left_image_bound_to_data.keys())
    state_one_steps = 0
    for i in range(len(timestamps)-1,-1,-1):
        if left_image_bound_to_data[timestamps[i]]['state'] == 1.0:
            state_one_steps += 1
        else:
            state_one_steps = 0
        left_image_bound_to_data[timestamps[i]]['state_one_steps'] = state_one_steps

    

    dst_path = opj(bag_folder_path,'.preprocessed')
    print """unix('mkdir -p ' """ +dst_path+')'
    unix('mkdir -p '+dst_path)

    print """save_obj(left_image_bound_to_data,opj(dst_path,'left_image_bound_to_data3')) """
    save_obj(left_image_bound_to_data,opj(dst_path,'left_image_bound_to_data3'))

    print """save_obj(preprocessed_data,opj(dst_path,'preprocessed_data3'))"""
    save_obj(preprocessed_data,opj(dst_path,'preprocessed_data3'))


    return preprocessed_data,left_image_bound_to_data

#
######################################################################
# 
#
########################## binding data to left_image timestamps ######
#

def _bind_left_image_timestamps_to_data(A):

    ms_timestamps = {}

    ms_timestamps['right_image'] = _assign_right_image_timestamps(A)

    for topic in single_value_topics:
        try:
            ms_timestamps[topic] = _interpolate_single_values(A,topic)
        except:
            print 'Error with topic '+topic
    for topic in vector3_topics:
        try:
            ms_timestamps[topic] = _interpolate_vector_values(A,topic)
        except:
            print 'Error with topic '+topic

    left_image_bound_to_data = {}

    error_log = []

    sorted_keys = sorted(A['left_image'].keys())
    for i in range(30,len(sorted_keys)-30):
    # we throw away the first and last 5 frames to avoid boundry problems with other sensors
        k = sorted_keys[i]
        left_image_bound_to_data[k] = {}
        for l in ms_timestamps.keys():
            try:
                left_image_bound_to_data[k][l] = ms_timestamps[l][k]
            except:
                error_log.append((k,l))
                left_image_bound_to_data[k][l] = 'no data'
                print (k,l)
    print error_log
    return left_image_bound_to_data,error_log


def _interpolate_single_values(A,topic):
    """
    Warning, this will interpolate the topic 'state', which we do not want.
    """
    interp_dic = {}
    k,d = get_sorted_keys_and_data(A[topic])
    for i in range(0,len(k)-1):
        for j in range(int(k[i]*1000),int(k[i+1]*1000)):
            v = (d[i+1]-d[i])/(k[i+1]-k[i]) * (j/1000.-k[i])  + d[i]
            if 'GPS' not in topic:
                v = round(v,3)
            interp_dic[j/1000.] = v
    return interp_dic

def _interpolate_vector_values(A,topic):
    interp_dic = {}
    k,d = get_sorted_keys_and_data(A[topic])
    d = np.array(d)
    dim = len(d[0])
    for i in range(0,len(k)-1):
        for j in range(int(k[i]*1000),int(k[i+1]*1000)):
            v = []
            for u in range(dim):
                if topic != 'gps': # with GPS we need as many decimal places as possible
                    v.append(  round((d[i+1,u]-d[i,u])/(k[i+1]-k[i]) * (j/1000.-k[i])  + d[i,u], 3))
                else:
                    v.append((d[i+1,u]-d[i,u])/(k[i+1]-k[i]) * (j/1000.-k[i])  + d[i,u])
            interp_dic[j/1000.] = v
    return interp_dic

def _assign_right_image_timestamps(A):
    interp_dic = {}
    k,d = get_sorted_keys_and_data(A['right_image'])
    for i in range(0,len(k)-1):
        a = int(k[i]*1000)
        b = int(k[i+1]*1000)
        c = (a+b)/2
        for j in range(a,b):
            if j < c:
                v = k[i]
            else:
                v = k[i+1]
            interp_dic[j/1000.] = v
    return interp_dic
#
######################################################################



def load_images_from_bag(bag_file_path,color_mode="rgb8"):
    print "loading " + bag_file_path
    bag_img_dic = {}
    bag_img_dic['left'] = {}
    bag_img_dic['right'] = {}
    sides=['left','right']
    bag = rosbag.Bag(bag_file_path)
    for side in sides:
        for m in bag.read_messages(topics=['/bair_car/zed/'+side+'/image_rect_color']):
            t = round(m.timestamp.to_time(),3)
            bag_img_dic[side][t] = bridge.imgmsg_to_cv2(m[1],color_mode)
    return bag_img_dic


def save_grayscale_quarter_images(bag_folder,bag_filename):
    b = load_images_from_bag(opj(bag_folder,bag_filename),color_mode="rgb8")
    for s in ['left','right']:
        for t in b[s]:
            b[s][t] = b[s][t][:,:,1]
            b[s][t] = imresize(b[s][t],0.25)
    unix('mkdir -p '+opj(bag_folder,'.preprocessed'))
    save_obj(b,opj(bag_folder,'.preprocessed',bag_filename))

def save_grayscale_quarter_bagfolder(bag_folder_path):
    bag_files = sorted(glob.glob(opj(bag_folder_path,'*.bag')))
    for b in bag_files:
        b = b.split('/')[-1]
        save_grayscale_quarter_images(bag_folder_path,b)
