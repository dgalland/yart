# Designing YART

## Multithreaded Multiprocessing

We can consider two categories of tasks

- I/O intensive e.g. camera capture, network send/receive, file read/write.
- Processor intensive e.g.: image processing algorithms

#### Multithread 

A thread is a flow of execution within a process.

The main advantage of multithreading is that it allows simultaneous I/O operations with processing

For example, on the PI side, we have

- Capture, exchange between the application and the camera
- Sending the image on the network

The execution of these two operations in separate threads allows concurrency, otherwise they would be serialized. The threads share the global data of the application, for example the camera object. Python provides tools for synchronization and exchange between threads (Event, Queue, ...)

Warning:

The Python interpreter has a limitation that does not allow the simultaneous execution of Python code in threads. Python multithreading is therefore only suitable for input-output tasks, it does not bring any gain for the simultaneity of computational tasks. It is then necessary to use multi processing

#### Multiprocessing

These are distinct processes which can then be executed on different processor cores.
The programming is more complex because the processes do not share the data in memory.
Inter-process communication mechanisms must be used.

#### PI side needs

- Non-blocking reception of client commands -> One thread, the main thread

- Control of the stepper motor, sending the PWM signal to the GPIO 
  We use the excellent and efficient pigpio package which allows to easily control the GPIO pins of the Raspberry.
  The main advantage of using pigpio is that the PWM signal to run the motor is done in a daemon process external to the application. So there is no need to provide a thead or a python process for this.

- Exchange with the camera, capture of the frame -> One thread

- Sending the frame on the network -> One thread
  Exchange of frames between the capture frame and the send frame by a Queue

In conclusion the CPU load on the PI is low, no need for multi-processing
A simple multithread with three Threads and one Queue are enough for the needs
Multiplying the threads would not bring anything more since the camera and the network are non-shareable resources

#### PC side needs

- Reactivity of the graphic interface -> One thread, the main thread
  Sending commands on the command connection

- Receiving frames -> One receiving thread
- Frame processing -> After receiving the frame, image processing is carried out on the PC but a priori its speed is sufficient to execute them in the receiving thread. If this is not the case, multithreading or multi-processing (in Python) should be considered.

#### Performance measurement and verification:

The aim is to determine the blocking points that could be improved for a better performance. We ask ourselves the question, is it the camera, the network, the CPU of the Pi, the CPU of the PC? We measure the CPU and network performance with the usual tools on the PC and the PI

In the current configuration, we see that:

- The 100Mb Ethernet network is just enough, but we have to watch it
- The PC, in my case a Core I7-4790, is sufficient. Do not launch big processing like encoding or other simultaneously!
- There is almost never a slowdown due to the network or the PC 
- The blocking point is the speed of capture in the exchange with the camera.



## Network programming MessageSocket.py

Basically, client-server communication involves a TCP socket. A TCP socket is a bidirectional data stream between the client and the server. On this data stream bytes are sent or received. It is therefore a fairly low level communication.

In the MessageSocket.py script we define a class and various methods for a higher level of communication

- Send/receive an array of bytes of a certain length
- Send/receive a NumPy array with its dimensions (an RGB image for example)
- Send/receive any Python object 

This last method makes exchanges much easier. For example, you can easily send/receive a command with its arguments in a list or a list of object attributes in a name/value dictionary.

The object is serialized into a string. The transmitted string is evaluated on receipt to reconstruct the object. See the code for the magic of this evaluation in Python!

Two network connections are used, one for sending command/response and the other for transmitting information headers and frames.

## Parameters, attributes

The application handles many parameters or attributes for the camera and the motor. These parameters are treated in an object-oriented way as attributes of the TelecineCamera class derived from PiCamera and TelecineMotor.

For the camera, these parameters include the attributes of the PiCamera base class (shuter_speed, resolution, awb_gains, ...) augmented by those of the derived TelecineCamera class.

Two generic methods getSettings and setSettings allow to set or retrieve the attributes of an object from a Name-Value dictionary.

For backup/restore, the parameter dictionary can be written and read in a npz file (camera.npz, motor.npz, ...).

The parameter dictionaries can also be easily exchanged as objects over the network.

With this design adding an attribute requires only a few lines of code.

## GPIO programming TelecineMotor.py

We use the excellent and efficient pigpio package which allows to easily control the Raspberry GPIO pins.
The main advantage of using pigpio is that the PWM signal for the motor as well as the control of the pins like the trigger is done by a daemon process external to the application, so there is no need to create a thead or a process for this.

The PWM signal is modulated at startup for a smooth startup and not abrupt which could be blocking

## Camera control  

The excellent PiCamera library, simple and efficient, allows to control the camera in Python. Note that it does not come from the Raspberry foundation but from an independent developer. It is no longer maintained by this developer nor by the foundation, which is very regrettable. It is however stable, without major bugs and works well even with the new HQ camera.

Its documentation is excellent, especially its description of the Picamera hardware, recommended consultation!

The capture of a single image "Shot" does not pose any difficulty.

Special attention is paid to the most efficient continuous capture with the "capture_sequence" method. This is the most delicate part of the code, including the processing of HDR bracketing.

The images are captured in jpeg on the video port stacked in a Queue to the network sending thread.

Before the image is transmitted a dictionary header with information about the image. These headers are also used to transmit any useful information between the PI and the PC.



## PC side

#### Graphical interface

The graphical interface is built with PyQT. The PyQT designer is used to create the TelecineApplication.ui interface

#### Image processing on the PC ImageThread.py

In the simplest case, the received jpeg image is displayed and directly saved in a file.

If it needs to be processed, it is decoded into an opencv BGR image (a numpy array).

The processing consists of a Mertens fusion if bracket

As explained above, in the current state of the application, the power of the PC is sufficient a priori to carry out the processing and display directly in the receiving thread.  If this were not the case, the frames would have to be distributed in processing processes (and not in threads since we are in Python)