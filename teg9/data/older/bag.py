
from kzpy3.vis import *
import rospy
import rosbag
import cv2
from cv_bridge import CvBridge,CvBridgeError
import threading
#import kzpy3.data_analysis.aruco_tools.aruco_annotator as ann
import kzpy3.teg9.data.nodes.arduino_node as ard

#face_cascade = cv2.CascadeClassifier('cars.xml')
bridge = CvBridge()

image_topics = ['left_image','right_image']
single_value_topics = ['steer','state','motor','encoder','GPS2_lat']
vector3_topics = ['acc','gyro','gyro_heading']#,'gps']
camera_sides = ['left','right']



def multi_preprocess(A,bag_folder_path,bagfile_range=[]):
    bag_files = sorted(gg(opj(bag_folder_path,'*.bag')))
    if len(bagfile_range) > 0:
        bag_files = bag_files[bagfile_range[0]:bagfile_range[1]]
    threading.Thread(target=multi_preprocess_thread,args=[A,bag_files]).start()


def multi_preprocess_thread(A,bag_files):
    for b in bag_files:
        if A['STOP_LOADER_THREAD']:
            A['STOP_LOADER_THREAD'] = False
            print('Stopping multi_preprocess_thread.')
            break
        preprocess(A,b)


def preprocess(A,path):
    timer = Timer(0)

    for topic in image_topics + single_value_topics:
        if topic not in A:

            A[topic] = []
    for topic in vector3_topics:
        if topic+'_x' not in A:
            A[topic+'_x'] = []
            A[topic+'_y'] = []
            A[topic+'_z'] = []

    if True:#try:
        cprint('Loading bagfile '+path,'yellow')

        bag = rosbag.Bag(path)

        for topic in single_value_topics:
            for m in bag.read_messages(topics=['/bair_car/'+topic]):
                t = round(m.timestamp.to_time(),3) # millisecond resolution
                if not isinstance(m[1].data,(int,long,float)):
                    print("if not isinstance(m[1].data,(int,long,float)):")
                    print(d2s("m[1].data = ",m[1].data))
                    assert(False)
                #A[topic][t] = m[1].data
                A[topic].append([t,m[1].data])
        
        for topic in vector3_topics:
            if topic != 'gps':
                for m in bag.read_messages(topics=['/bair_car/'+topic]):
                    t = round(m.timestamp.to_time(),3)
                    if not isinstance(m[1].x,(int,long,float)):
                        print("if not isinstance(m[1].x,(int,long,float)):")
                        print(d2s("m[1].x = ",m[1].x))
                        assert(False)
                    if not isinstance(m[1].y,(int,long,float)):
                        print("if not isinstance(m[1].y,(int,long,float)):")
                        print(d2s("m[1].y = ",m[1].y))
                        assert(False)
                    if not isinstance(m[1].z,(int,long,float)):
                        print("if not isinstance(m[1].x,(int,long,float)):")
                        print(d2s("m[1].z = ",m[1].z)) 
                        assert(False)
                    A[topic+'_x'].append([t,m[1].x])
                    A[topic+'_y'].append([t,m[1].y])
                    A[topic+'_z'].append([t,m[1].z])

        color_mode = "rgb8"

        for s in camera_sides:
            for m in bag.read_messages(topics=['/bair_car/zed/'+s+'/image_rect_color']):
                t = round(m.timestamp.to_time(),3)
                if A['t_previous'] > 0:            
                    if s == 'left':
                        A['left_deltas'].append([t,t-A['t_previous']])
                A['t_previous'] = t
                
                A[s+'_image'].append([t,bridge.imgmsg_to_cv2(m[1],color_mode)])
    #except Exception as e:
    #    print e.message, e.args
    print(d2s('Done in',timer.time(),'seconds'))


def graph_thread(A):
    figure('MSE')
    indx = int(A['current_img_index'])
    while True:
        while A['STOP_GRAPH_THREAD'] == False:   
            if len(A['left_image']) < 3*30:
                #print("""'if len(A['left_image']) < 30:'""")
                pause(0.1)
                continue
            A_len = len(A['left_image'])
            clf()       
            steer = array(A['steer'])
            plot(steer[:,0]-steer[0,0],steer[:,1])
            t = A['left_image'][indx][0]
            xlim(t-20-steer[0,0],t-steer[0,0])
            motor = array(A['motor'])
            plot(motor[:,0]-motor[0,0],motor[:,1])

            N = 30
            acc_x = array(A['acc_x'])
            acc_y = array(A['acc_y'])
            acc_z = array(A['acc_z'])

            
            acc_x_smooth = 1.*acc_x
            for i in range(N,len(acc_x)):
                acc_x_smooth[i,1] = acc_x[i-N:i,1].mean()
            acc_y_smooth = 1.*acc_x
            for i in range(N,len(acc_y)):
                acc_y_smooth[i,1] = acc_y[i-N:i,1].mean()
            acc_z_smooth = 1.*acc_z
            for i in range(N,len(acc_z)):
                acc_z_smooth[i,1] = acc_z[i-N:i,1].mean()

            #acc_x_smooth[:,1] -= acc_x[:,1].mean()
            #acc_y_smooth[:,1] -= acc_y[:,1].mean()
            #acc_z_smooth[:,1] -= acc_z[:,1].mean()
            acc_xyz = 1.*acc_x_smooth
            acc_xyz[:,1] = sqrt(acc_x_smooth[:,1]**2+acc_z_smooth[:,1]**2)

            plot(acc_x_smooth[:,0]-acc_x_smooth[0,0],acc_x_smooth[:,1])
            plot(acc_y_smooth[:,0]-acc_y_smooth[0,0],acc_y_smooth[:,1])
            plot(acc_z_smooth[:,0]-acc_z_smooth[0,0],acc_z_smooth[:,1])
            plot(acc_xyz[:,0]-acc_z_smooth[0,0],acc_xyz[:,1])

            #plot(acc_y[:,0]-acc_y[0,0],acc_y[:,1])
            #plot(acc_z[:,0]-acc_z[0,0],acc_z[:,1])
            ylim(-15,105)
            if False: #hist_timer.check():
                figure('left_deltas')
                left_deltas = array(A['left_deltas'])
                hist(left_deltas[:,1])
                hist_timer.reset()
                figure('MSE')

            pause(0.001)
            while A_len == len(A['left_image']):
                indx = int(A['current_img_index'])
                t = A['left_image'][indx][0]
                xlim(t-20-steer[0,0],t-steer[0,0])
                pause(0.2)
        pause(0.2)


def animator_thread(A):
    #lock = threading.Lock()
    q_lst = []
    #print("MAKE SURE TO CALIBRATE TRANSMITTER!!!")
    while True:
        while A['STOP_ANIMATOR_THREAD'] == False:
            #lock.acquire()
            if len(A['left_image']) < 2*30:
                #print(d2n("len(A['left_image']) =",len(A['left_image'])))
                time.sleep(0.1)
                continue
            if False:
                steer_percent,motor_percent = ard.query_states()
                #print steer_percent
                #if abs(steer_percent-49)>2:
                #    print "**********************************"
                s = 0
                q = 0
                
                if steer_percent != None and motor_percent != None:
                    #print states[0]
                    q = 1.0-steer_percent/99.
                    s = (motor_percent - 49.0)
                    if abs(s) < 2:
                        s = 0.0
                    s = s/10.0+1
                    if abs(s) > 3:
                        s *= 2
                    A['d_indx'] = s
            A['current_img_index'] += A['d_indx']
            if A['current_img_index'] >= len(A['left_image']):
                A['current_img_index'] = len(A['left_image'])-1
            elif A['current_img_index'] < 0:
                A['current_img_index'] = 0
            indx = int(A['current_img_index'])
            img = A['left_image'][indx][1].copy()
            if False:
                p = int(q*shape(img)[1])
                if p < 0:
                    p = 0
                elif p >= shape(img)[1]:
                    p = shape(img)[1]-1
                #if abs(q-0.5) >0: # 0.1:
                img[:,p,:] = 255
            cv2.imshow('animate',cv2.cvtColor(img,cv2.COLOR_RGB2BGR))
            k = cv2.waitKey(33)

            if k == ord(' '):
                A['d_indx'] = 0
            if k == ord('1'):
                A['d_indx'] = 1
            if k == ord('2'):
                A['d_indx'] = 2
            if k == ord('3'):
                A['d_indx'] = 3
            if k == ord('4'):
                A['d_indx'] = 4
            if k == ord('5'):
                A['d_indx'] = 7
            if k == ord('6'):
                A['d_indx'] = 10
            if k == ord('7'):
                A['d_indx'] = 15
            if k == ord('8'):
                A['d_indx'] = 20
            if k == ord('9'):
                A['d_indx'] = 30   

            if k == ord('!'):
                A['d_indx'] = -1
            if k == ord('@'):
                A['d_indx'] = -2
            if k == ord('#'):
                A['d_indx'] = -3
            if k == ord('$'):
                A['d_indx'] = -4
            if k == ord('%'):
                A['d_indx'] = -7
            if k == ord('^'):
                A['d_indx'] = -10
            if k == ord('&'):
                A['d_indx'] = -15
            if k == ord('*'):
                A['d_indx'] = -20
            if k == ord('('):
                A['d_indx'] = -30

            if k == ord('w'):
                print("car ahead")
            if k == ord('a'):
                print("car left")
            if k == ord('d'):
                print("car right")

            if k == ord('b'):
                A['current_img_index'] -= 2*30
                if A['current_img_index'] < 0:
                    A['current_img_index'] = 0
            #print k

            #mi_or_cv2(img[1],cv=True,delay=30,title='animate')
        time.sleep(0.2)

def d_index_up(A):
    lock = threading.Lock()
    lock.acquire()
    A['d_indx'] += 0.2
    lock.release()
    print(d2s("A['d_indx'] =",A['d_indx']))
def d_index_down(A):
    lock = threading.Lock()
    lock.acquire()
    A['d_indx'] -= 0.2
    lock.release()
    print(d2s("A['d_indx'] =",A['d_indx']))

def start_graph(A):
    A['STOP_GRAPH_THREAD'] = False
def stop_graph(A):
    A['STOP_GRAPH_THREAD'] = True
def start_animation(A):
    A['STOP_ANIMATOR_THREAD'] = False
def stop_animation(A):
    A['STOP_ANIMATOR_THREAD'] = True
def stop_loader(A):
    A['STOP_LOADER_THREAD'] = True


def get_new_A(_=None):
    A = {}
    A['STOP_LOADER_THREAD'] = False
    A['STOP_ANIMATOR_THREAD'] = False
    A['STOP_GRAPH_THREAD'] = False
    A['d_indx'] = 1.0
    A['current_img_index'] = -A['d_indx']
    A['t_previous'] = 0
    A['left_deltas'] = []
    return A

def menu(A):
    menu_functions = ['exit_menu','start_animation','start_graph','stop_animation','stop_graph','stop_loader','get_new_A','d_index_up','d_index_down']
    while True:
        for i in range(len(menu_functions)):
            print(d2n(i,') ',menu_functions[i]))
        try:
            choice = input('> ')
            if type(choice) == int:
                if choice == 0:
                    return
                if choice >-1 and choice < len(menu_functions):
                    exec_str = d2n(menu_functions[choice],'(A)')
                    exec(exec_str)
        except:
            pass



if __name__ == '__main__':
    bag_folder_path = sys.argv[1]
    bagfile_range=[int(sys.argv[2]),int(sys.argv[3])]
    hist_timer = Timer(10)
    A = {}
    A = get_new_A(A)
    multi_preprocess(A,bag_folder_path,bagfile_range)
    threading.Thread(target=animator_thread,args=[A]).start()
    #threading.Thread(target=graph_thread,args=[A]).start()
    menu(A)





