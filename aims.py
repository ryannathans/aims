#! /usr/bin/python
# -*- coding: utf-8 -*-

# import external libraries
import wx # 2.8 on unix, 3.0 on windows (PySimpleApp deprecated idgaf)
import wx.lib.newevent #needed for creating new events, not included in import wx
import vlc

# import standard libraries
import sys
import os
import user
import socket
import select
import time
import datetime
from threading import Thread

##### client configuration
serversocket = ('localhost', 6969) #host to connect to, port

##### server configuration
hostsocket = ('0.0.0.0', 6969) #ip/host, port

# Aims - Automatic Interplatform Media Synchronizer
# Shared Media Playing based on WX example for VLC Python bindings
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston MA 02110-1301, USA.

if len(sys.argv) == 2 and sys.argv[1] == 'server': isserver = True
else: isserver  = False

def formatSeconds(seconds):
	hrdivmod = divmod(seconds, 3600)
	hours = hrdivmod[0]
	seconds = hrdivmod[1]
	
	mindivmod = divmod(seconds, 60)
	minutes = mindivmod[0]
	seconds = mindivmod[1]
	
	return "%02i:%02i:%02i" % (hours, minutes, seconds)

def sendData(sock, data):
    while select.select([],[conn],[],0)[1] != [] and sock.send(data) != 1: 
        #FIXME: Make this support packets longer than a byte
        pass

def checkNetwork():
    global received
    lastping = datetime.datetime.now()
    while shutdown == False:
        
        if select.select([],[],[conn],0)[2] != []:
            print('Broken network?') #FIXME: reconnect/etc? when does this happen? No fucking clue.
            sys.exit(1)
        
        while select.select([conn],[],[],0)[0] != []:
            received.append(conn.recv(1))
        
        for packet in received:
            evt = None
            if packet == 'r':
                evt = NetworkCommandEvent(eventtype='resume')
            elif packet == 'p':
                evt = NetworkCommandEvent(eventtype='pause')
            elif packet == 'o':
                evt = NetworkCommandEvent(eventtype='open', filename= u'video.mp4')
                #FIXME: allow adjustable filename via network
            elif packet == '1':
                sendData(conn, '2') #replying to ping
            elif packet == '2':
                lastping = datetime.datetime.now() #reply from ping
            
            if evt != None:
                wx.PostEvent(player, evt)
            
            received = received[1:]
            
            
        now = datetime.datetime.now()
        if now - lastping >= datetime.timedelta(seconds=15):
            print("Network timeout, 15 seconds passed without connection")
            #FIXME: Do something about this
        elif now - lastping >= datetime.timedelta(seconds=5):
            sendData(conn, '1')
        
        
        time.sleep(0.01) #check/process actions every 10ms + thread overhead (adjustable)

shutdown = False
received = [] #stuff in list when executing

if isserver:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for x in xrange(0,20):
        print("Attempt " + str(x+1) + " to bind to server address")
        try:
            sock.bind(hostsocket)
            break
        except:
            print("Failed to bind to address")
            time.sleep(3)
    print("Set up server socket")
    print("Waiting for client connection...")
    sock.listen(1) #will eventually allow multiple clients, so synchronization between 3/4/5/? users
    conn, port = sock.accept()
    sock.close()
    print("Connected!")
else:
    conn = socket.create_connection(serversocket)
    port = conn.getsockname()[1]
conn.setblocking(0)

NetworkCommandEvent, EVT_NETCMD = wx.lib.newevent.NewEvent()

class Player(wx.Frame):
    """The main window has to deal with events.
    """
    
    def __init__(self, title):
        wx.Frame.__init__(self, None, -1, title,
                          pos=wx.DefaultPosition, size=(700, 550))
                          
        self.networkThread = Thread(target=checkNetwork)
        self.networkThread.start()
        
        self.Bind(EVT_NETCMD, self.OnNetworkCommand)
        
        # Menu Bar
        #   File Menu
        self.frame_menubar = wx.MenuBar()
        self.file_menu = wx.Menu()
        self.file_menu.Append(1, "&Open", "Open from file..")
        self.file_menu.AppendSeparator()
        self.file_menu.Append(2, "&Close", "Quit")
        self.Bind(wx.EVT_MENU, self.OnOpen, id=1)
        self.Bind(wx.EVT_MENU, self.OnExit, id=2)
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.frame_menubar.Append(self.file_menu, "File")
        self.SetMenuBar(self.frame_menubar)

        # Panels
        # The first panel holds the video and it's all black
        self.videopanel = wx.Panel(self, -1)
        self.videopanel.SetBackgroundColour(wx.BLACK)

        # The second panel holds controls
        ctrlpanel = wx.Panel(self, -1 )
        self.timeslider = wx.Slider(ctrlpanel, -1, 0, 0, 1000)
        self.timeslider.SetRange(0, 1000)
        pause  = wx.Button(ctrlpanel, label="Pause")
        play   = wx.Button(ctrlpanel, label="Play")
        stop   = wx.Button(ctrlpanel, label="Stop")
        volume = wx.Button(ctrlpanel, label="Volume")
        self.timetext = wx.StaticText(ctrlpanel, label="00:00:00 / 00:00:00")
        self.volslider = wx.Slider(ctrlpanel, -1, 0, 0, 100, size=(100, -1))

        # Bind controls to events
        self.Bind(wx.EVT_BUTTON, self.OnPlay, play)
        self.Bind(wx.EVT_BUTTON, self.OnPause, pause)
        self.Bind(wx.EVT_BUTTON, self.OnStop, stop)
        self.Bind(wx.EVT_BUTTON, self.OnToggleVolume, volume)
        self.Bind(wx.EVT_SLIDER, self.OnSetVolume, self.volslider)

        # Give a pretty layout to the controls
        ctrlbox = wx.BoxSizer(wx.VERTICAL)
        box1 = wx.BoxSizer(wx.HORIZONTAL)
        box2 = wx.BoxSizer(wx.HORIZONTAL)
        # box1 contains the timeslider
        box1.Add(self.timeslider, 1)
        # box2 contains some buttons and the volume controls
        box2.Add(play, flag=wx.RIGHT, border=5)
        box2.Add(pause)
        box2.Add(stop)
        box2.Add(self.timetext, flag=wx.LEFT|wx.TOP, border=5)
        box2.Add((-1, -1), 1)
        box2.Add(volume)
        box2.Add(self.volslider, flag=wx.TOP | wx.LEFT, border=5)
        # Merge box1 and box2 to the ctrlsizer
        ctrlbox.Add(box1, flag=wx.EXPAND | wx.BOTTOM, border=10)
        ctrlbox.Add(box2, 1, wx.EXPAND)
        ctrlpanel.SetSizer(ctrlbox)
        # Put everything togheter
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.videopanel, 1, flag=wx.EXPAND)
        sizer.Add(ctrlpanel, flag=wx.EXPAND | wx.BOTTOM | wx.TOP, border=10)
        self.SetSizer(sizer)
        self.SetMinSize((350, 300))

        # finally create the timer, which updates the timeslider
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)

        # VLC player controls
        self.Instance = vlc.Instance()
        self.player = self.Instance.media_player_new()

    def OnNetworkCommand(self, evt):
        #passing evt to event handlers so that extra transmitted data can be passed eventually
        #ie: filename, time sync, etc.
        if evt.eventtype == 'resume':
            self.OnPlay(evt)
        elif evt.eventtype == 'pause':
            self.OnPause(evt)
        elif evt.eventtype == 'open':
            self.OnOpen(evt)

    def OnExit(self, evt):
        """Closes the window.
        """
        global shutdown
        shutdown = True
        time.sleep(0.1)
        sys.exit(0)

    def OnOpen(self, evt):
        """Pop up a new dialow window to choose a file, then play the selected file.
        """
        
        try:
            if evt.eventtype == 'open':
                netevent = True
            else:
                netevent = False
        except:
            netevent = False

        if not netevent:
            global conn
            while conn.send('o') != 1:
                pass
        
        # if a file is already running, then stop it.
        self.OnStop(evt)

        # Create a file dialog opened in the current home directory, where
        # you can display all kind of files, having as title "Choose a file".
        
        if not netevent:
            dlg = wx.FileDialog(self, "Choose a file", user.home, "", "*.*", wx.OPEN)
            returnstatus = dlg.ShowModal() == wx.ID_OK

		
        if not netevent and returnstatus:
            dirname = dlg.GetDirectory()
            filename = dlg.GetFilename()
        elif netevent:
            dirname = os.getcwdu()
            filename = evt.filename
        
        if (not netevent and returnstatus) or netevent:
            # Creation
            self.Media = self.Instance.media_new(unicode(os.path.join(dirname, filename)))
            self.player.set_media(self.Media)
            # Report the title of the file chosen
            title = self.player.get_title()
            #  if an error was encountred while retriving the title, then use filename
            if title == -1:
                title = filename
            self.SetTitle("%s - Aims" % title)

            # set the window id where to render VLC's video output
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.videopanel.GetHandle())
                #self.videopanel.GetHandle() don't know why this is commented but it works...
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.videopanel.GetHandle())
            else:
                self.player.set_nsobject(self.videopanel.GetHandle())
            
            #self.OnPlay(evt) let's not play, just queue the video for playback

            # set the volume slider to the current volume
            self.volslider.SetValue(self.player.audio_get_volume() / 2)
            
        if not netevent:
            # finally destroy the dialog
            dlg.Destroy()

    def OnPlay(self, evt):
        """Toggle the status to Play/Pause.

        If no file is loaded, open the dialog window.
        """
        # check if there is a file to play, otherwise open a
        # wx.FileDialog to select a file
        if not self.player.get_media():
            self.OnOpen(None)
        else:
        
            global conn
            
            if self.player.get_state() != vlc.State.Playing and received == []:
                while conn.send('r') != 1:
                    pass #keep trying to send data
            
            # Try to launch the media, if this fails display an error message
            if self.player.play() == -1:
                self.errorDialog("Unable to play.")
            else:
                self.timer.Start()

    def OnPause(self, evt):
        """Pause the player.
        """
        global conn
        
        if self.player.get_state() == vlc.State.Playing and received == []:
                while conn.send('p') != 1:
                    pass #keep trying to send data
        
        if self.player.get_state() != vlc.State.Paused:
            self.player.pause()

    def OnStop(self, evt):
        """Stop the player.
        """
        self.player.stop()
        # reset the time slider
        self.timeslider.SetValue(0)
        self.timer.Stop()

    def OnTimer(self, evt):
        """Update the time slider according to the current movie time.
        """
        
        # since the self.player.get_length can change while playing,
        # re-set the timeslider to the correct range.
        length = self.player.get_length()
        self.timeslider.SetRange(-1, length)

        # update the time on the slider
        time = self.player.get_time()
        self.timeslider.SetValue(time)

        self.timetext.SetLabel("%s / %s" % (formatSeconds(time/1000),formatSeconds(length/1000)))
    def OnToggleVolume(self, evt):
        """Mute/Unmute according to the audio button.
        """
        is_mute = self.player.audio_get_mute()

        self.player.audio_set_mute(not is_mute)
        # update the volume slider;
        # since vlc volume range is in [0, 200],
        # and our volume slider has range [0, 100], just divide by 2.
        self.volslider.SetValue(self.player.audio_get_volume() / 2)

    def OnSetVolume(self, evt):
        """Set the volume according to the volume sider.
        """
        volume = self.volslider.GetValue() * 2
        # vlc.MediaPlayer.audio_set_volume returns 0 if success, -1 otherwise
        if self.player.audio_set_volume(volume) == -1:
            self.errorDialog("Failed to set volume")


    def errorDialog(self, errormessage):
        """Display a simple error dialog.
        """
        edialog = wx.MessageDialog(self, errormessage, 'Error', wx.OK|
                                                                wx.ICON_ERROR)
        edialog.ShowModal()

if __name__ == "__main__":
    # Create a wx.App(), which handles the windowing system event loop
    app = wx.PySimpleApp()
    # Create the window containing our small media player
    player = Player("Simple PyVLC Player")
    # show the player window centred and run the application
    player.Centre()
    player.Show()
    app.MainLoop()
