#!/usr/bin/env python

###########################################################################################
# n900-encode.py: Encode almost any Video to an Nokia N900-compatible format (h264,aac,mp4)
# Disclaimer: This program is provided without any warranty, USE AT YOUR OWN RISK!
#
# Version 1.2 (23.03.2012)
#
# (C) 2010-2012 Stefan Brand <seiichiro@seiichiro0185.org>
#
# This programm is licensed under the Terms of the GPL Version 3
# See COPYING for more info.
#
###########################################################################################

import sys, os, getopt, subprocess, re, atexit
from signal import signal, SIGTERM, SIGINT
from time import sleep

###########################################################################################
# Default values, feel free to adjust
###########################################################################################

_basewidth = 854 		# Base width for widescreen Video
_basewidth43 = 640	# Base width for 4:3 Video
_maxheight = 480		# maximum height allowed
_abitrate = 112			# Audio Bitrate in kBit/s
_vbitrate = 22			# Video Bitrate in kBit/s, Values < 52 are used as a CRF-Factor
_threads = "auto"		# Use n Threads to encode
_mpbin = None				# mplayer binary, if set to None it is searched in your $PATH
_ffbin = None				# ffmpeg binary, if set to None it is searched in your $PATH

###########################################################################################
# Main Program, no changes needed below this line
###########################################################################################

# Global Variables

mda = None
mdv = None
afifo = None
vfifo = None

# Main Function
def main(argv):
	"""Main Function, cli argument processing and checking"""

	# CLI Argument Processing
	try:
		opts, args = getopt.getopt(argv, "i:o:m:v:a:t:hf", ["input=", "output=", "mpopts=", "abitrate=", "vbitrate=", "threads=", "help", "force-overwrite"])
	except getopt.GetoptError as err:
		printi(str(err))
		usage()

	input = None
	output = "n900encode.mp4"
	mpopts = ""
	abitrate = _abitrate * 1000
	vbitrate = int(_vbitrate)
	threads = _threads
	overwrite = False
	for opt, arg in opts:
		if opt in ("-i", "--input"):
			input = arg
		elif opt in ("-o" "--output"):
			output = arg
		elif opt in ("-m" "--mpopts"):
			mpopts = arg
		elif opt in ("-a", "--abitrate"):
			abitrate = int(arg) * 1000
		elif opt in ("-v", "--vbitrate"):
			vbitrate = int(arg)
		elif opt in ("-t", "--threads"):
			threads = arg
		elif opt in ("-f", "--force-overwrite"):
			overwrite = True
		elif opt in ("-h", "--help"):
			usage()

	# Check for needed Programs
	global mpbin
	mpbin = None
	if not _mpbin == None and os.path.exists(_mpbin) and not os.path.isdir(_mpbin):
		mpbin = _mpbin
	else:
		mpbin = progpath("mplayer")
	if mpbin == None:
		print("Error: mplayer not found in PATH and no binary given, Aborting!")
		sys.exit(1)

	global ffbin
	ffbin = None
	if not _ffbin == None and os.path.exists(_ffbin) and not os.path.isdir(_ffbin):
		ffbin = _ffbin
	else:
		ffbin = progpath("ffmpeg")
	if ffbin == None:
		print( "Error: ffmpeg not found in PATH and no binary given, Aborting!")
		sys.exit(1)

	# Check input and output files
	if not os.path.isfile(input):
		print("Error: input file is not a valid File or doesn't exist")
		sys.exit(2)

	if os.path.isfile(output):
		if overwrite:
			os.remove(output)
		else:
			print("Error: output file " + output + " already exists, force overwrite with -f")
			sys.exit(1)

	# Start Processing
	res = calculate(input)
	convert(input, output, res, abitrate, vbitrate, threads, mpopts)
	sys.exit(0)


def calculate(input):
	"""Get Characteristics from input video and calculate resolution for output"""

	# Get characteristics using mplayer
	cmd=[mpbin, "-ao", "null", "-vo", "null", "-frames", "0", "-identify", input]
	mp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()

	try:
		s = re.compile("^ID_VIDEO_ASPECT=(.*)$", re.M)
		m = s.search(bytes.decode(mp[0]))
		orig_aspect = m.group(1)
		s = re.compile("^ID_VIDEO_WIDTH=(.*)$", re.M)
		m = s.search(bytes.decode(mp[0]))
		orig_width = m.group(1)
		s = re.compile("^ID_VIDEO_HEIGHT=(.*)$", re.M)
		m = s.search(bytes.decode(mp[0]))
		orig_height = m.group(1)
	except:
		print("Error: unable to identify source video, exiting!")
		sys.exit(2)

	# Calculate output resolution
	if float(orig_aspect) == 0 or orig_aspect == "":
		orig_aspect = float(orig_width)/float(orig_height)
	width = _basewidth
	height = int(round(_basewidth / float(orig_aspect) / 16) * 16)
	if (height > _maxheight):
		width = _basewidth43
		height = int(round(_basewidth43 / float(orig_aspect) / 16) * 16)

	return (width, height)


def convert(input, output, res, abitrate, vbitrate, threads, mpopts):
	"""Convert the Video"""

	# Needed for cleanup function
	global afifo, vfifo, mda, mdv

	# Create FIFOs for passing audio/video from mplayer to ffmpeg
	pid = os.getpid()
	afifo = "/tmp/stream" + str(pid) + ".wav"
	vfifo = "/tmp/stream" + str(pid) + ".yuv"
	os.mkfifo(afifo)
	os.mkfifo(vfifo)

	# Define mplayer command for video decoding
	mpvideodec = [ mpbin,
			"-sws", "9",
			"-vf", "scale=" + str(res[0]) + ":" + str(res[1]) + ",dsize=" + str(res[0]) + ":" + str(res[1]) + ",unsharp=c4x4:0.3:l5x5:0.5", "-ass",
			"-vo", "yuv4mpeg:file=" + vfifo,
			"-ao", "null",
			"-nosound",
			"-noframedrop",
			"-benchmark",
			"-quiet",
			"-nolirc",
			"-msglevel", "all=-1",
			input ]
	for mpopt in mpopts.split(" "):
		mpvideodec.append(mpopt)

	# Define mplayer command for audio decoding
	mpaudiodec = [ mpbin,
			"-ao", "pcm:file=" + afifo,
			"-vo", "null",
			"-vc", "null",
			"-noframedrop",
			"-quiet",
			"-nolirc",
			"-msglevel", "all=-1",
			input ]
	for mpopt in mpopts.split(" "):
		mpaudiodec.append(mpopt)


	# Define ffmpeg command for a/v encoding

	if (vbitrate > 51):
		rmode = "-b:v"
		vbitr = str(vbitrate*1000)
	else:
		rmode = "-crf"
		vbitr = str(vbitrate)

	ffmenc = [ ffbin,
			"-f", "yuv4mpegpipe",
			"-i", vfifo,
			"-i", afifo,
			"-acodec", "aac",
			"-strict", "experimental",
			"-ac", "2",
			"-ab", str(abitrate),
			"-ar", "44100",
			"-vcodec", "libx264",
			"-threads", str(threads),
			"-vprofile", "baseline",
			"-tune", "animation",
			rmode, vbitr,
			"-flags", "+loop", "-cmp", "+chroma", "-coder", "0",
			"-partitions", "+parti4x4+partp8x8+partb8x8",
			"-subq", "7", "-trellis", "1", "-refs", "3",
			"-me_range", "16", "-me_method", "hex",
			"-bufsize", "10M", "-maxrate", "1000000",
			"-x264opts", "level=3.1", "-f", "mp4", 
			output ]

	# Start mplayer decoding processes in background
	try:
		mdv = subprocess.Popen(mpvideodec, stdout=None, stderr=None)
		mda = subprocess.Popen(mpaudiodec, stdout=None, stderr=None)
	except:
		print("Error: Starting decoding threads failed!")
		sys.exit(3)
	
	# Start ffmpeg encoding process in foreground
	try:
		subprocess.check_call(ffmenc)
	except subprocess.CalledProcessError:
		print("Error: Encoding thread failed!")
		sys.exit(4)


def progpath(program):
	"""Get Full path for given Program"""

	for path in os.environ.get('PATH', '').split(':'):
		if os.path.exists(os.path.join(path, program)) and not os.path.isdir(os.path.join(path, program)):
			return os.path.join(path, program)
	return None

def cleanup():
	"""Clean up when killed"""

	# give ffmpeg time to stop
	sleep(2)

	# Cleanup
	try:
		if (mda != None):
			os.kill(mda.pid())
		if (mdv != None):
			os.kill(mdv.pid())
	finally:
		if (afifo != None):
			os.remove(afifo)
		if (vfifo != None):
			os.remove(vfifo)
		os._exit(0)

def usage():
	"""Print avaiable commandline arguments"""

	print("This is n900-encode.py (C) 2010 Stefan Brand <seiichiro0185 AT tol DOT ch>")
	print("Usage:")
	print("  n900-encode.py --input <file> [opts]\n")
	print("Options:")
	print("  --input <file>    [-i]: Video to Convert")
	print("  --output <file>   [-o]: Name of the converted Video")
	print("  --mpopts \"<opts>\" [-m]: Additional options for mplayer (eg -sid 1 or -aid 1) Must be enclosed in \"\"")
	print("  --abitrate <br>   [-a]: Audio Bitrate in KBit/s")
	print("  --vbitrate <br>   [-v]: Video Bitrate in kBit/s, values less than 52 will be used as CRF-Factor")
	print("  --threads <num>   [-t]: Use <num> Threads to encode")
	print("  --force-overwrite [-f]: Overwrite output-file if existing")
	print("  --help            [-h]: Print this Help")
	os._exit(0)


# Start the Main Function
if __name__ == "__main__":
	# Catch kill and clean up
	atexit.register(cleanup)

	signal(SIGTERM, lambda signum, stack_frame: exit(1))
	signal(SIGINT, lambda signum, stack_frame: exit(1))

	# Check min params and start if sufficient
	if len(sys.argv) > 1:
		main(sys.argv[1:])
	else:
		print("Error: You have to give an input file at least!")
		usage()
