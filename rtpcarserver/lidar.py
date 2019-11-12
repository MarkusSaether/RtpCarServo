from rplidar import RPLidar
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.animation as animation
import server
PORT_NAME = '/dev/ttyUSB0'
DMAX = 3000
IMIN = 0
IMAX = 50


class Lidar:
    def __init__(self, port_name=PORT_NAME):
        self.lidar = RPLidar(port_name)
        self.observers = []
    
    def register(self, observer):
        if observer not in self.observers:
            self.observers.append(observer)
        else: print("Failed to add {}".format(observer))
        
    def remove(self, observer):
        try:
            selv.observer.remove(observer)
        except ValueError: print("Failed to remove {}".format(observer))

    def notify(self, frontAngles):
        for observer in self.observers:
            observer.listen(frontAngles)
    
    def scanner(self, num, iterator, line):
        scan = next(iterator)

        frontAngles = False
        for item in scan:
            if item[1] >= 0 and item[1] <= 44 and item[2] <= 1000 or item[1]<= 360 and item[1] >= 315 and item[2] <= 1000:
                frontAngles = True
                break
       #         frontAngles.append(item)
        self.notify(frontAngles)
        # print(frontAngles)
        
        offsets = np.array([(np.radians(meas[1]), meas[2]) for meas in scan])
        line.set_offsets(offsets)
        # print(offsets)
        intens = np.array([meas[0] for meas in scan])
        #test = np.array([meas[0] for meas in frontAngles])
        line.set_array(intens)
        return line

    def plot(self):
        fig = plt.figure()
        ax = plt.subplot(111, projection='polar')
        line = ax.scatter([0, 0], [0, 0], s=5, c=[IMIN, IMAX],
                          cmap=plt.cm.Greys_r, lw=0)
        ax.set_rmax(DMAX)
        ax.grid(True)

        iterator = self.lidar.iter_scans(1000)
        ani = animation.FuncAnimation(fig, self.scanner,
                                      fargs=(iterator, line), interval=100)
        plt.show()
        self.shutdown()

    def shutdown(self):
        self.lidar.stop()
        self.lidar.disconnect()

