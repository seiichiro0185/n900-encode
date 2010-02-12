#!/usr/bin/env python

import sys, os, getopt, subprocess, re

_basewidth = 800
_basewidth43 = 640
_maxheight = 480
_abitrate = 96
_vbitrate = 500
_threads = 2

def main(argv):
	"""Main Function, cli argument processing and checking"""
	try:
		opts, args = getopt.getopt(argv, "i:o:m:v:a:t:h", ["input=", "output=", "mpopts=", "abitrate=", "vbitrate=", "threads=", "help"])
	except getopt.GetoptError, err:
		print str(err)
		usage()
		sys.exit(1)
	input = None
	output = "n900encode,mp4"
	mpopts = ""
	abitrate = _abitrate * 1000
	vbitrate = _vbitrate * 1000
	threads = _threads
	for opt, arg in opts:
		if opt in ("-i", "--input"):
			input = arg
		elif opt in ("-o" "--output"):
			output = arg
		elif opt in ("-m" "--mpopts"):
			mpopts = arg
		elif opt in ("-a", "--abitrate"):
			abitrate = arg * 1000
		elif opt in ("-v", "--vbitrate"):
			vbitrate = arg * 1000
		elif opt in ("-t", "--threads"):
			threads = arg
		elif opt in ("-h", "--help"):
			usage()
			sys.exit(0)

	if not os.path.isfile(input):
		print "Error: input file is not a valid File or doesn't exist"
		sys.exit(2)
	
	res = calculate(input)
	convert(input, output, res, abitrate, vbitrate, threads, mpopts)


def calculate(input):
	cmd="mplayer -ao null -vo null -frames 0 -identify \"" + input + "\""
	mp = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
	
	s = re.compile("^ID_VIDEO_ASPECT=(.*)$", re.M)
	m = s.search(mp[0])
	orig_aspect = m.group(1)
	s = re.compile("^ID_VIDEO_WIDTH=(.*)$", re.M)
	m = s.search(mp[0])
	orig_width = m.group(1)
	s = re.compile("^ID_VIDEO_HEIGHT=(.*)$", re.M)
	m = s.search(mp[0])
	orig_height = m.group(1)

	width = _basewidth
	height = int(round(_basewidth / float(orig_aspect) / 16) * 16)
	if (height > _maxheight):
		width = _basewidth43
		height = int(round(_basewidth43 / float(orig_aspect) / 16) * 16)

	return (width, height)


def convert(input, output, res, abitrate, vbitrate, threads, mpopts):
	"""Convert the Video"""

	pid = os.getpid()
	afifo = "/tmp/stream" + str(pid) + ".wav"
	vfifo = "/tmp/stream" + str(pid) + ".yuv"
	os.mkfifo(afifo)
	os.mkfifo(vfifo)

	mpvideodec = "mplayer -sws 9 -vf scale=" + str(res[0]) + ":" + str(res[1]) + ",unsharp=c4x4:0.3:l5x5:0.5 -vo yuv4mpeg:file=" + vfifo +" -ao null -nosound -noframedrop -benchmark -quiet -msglevel all=-1 " + mpopts + "\"" + input + "\" &"

	mpaudiodec = "mplayer -ao pcm:file=" + afifo + " -vo null -vc null -noframedrop -quiet -msglevel all=-1 2>/dev/null " + mpopts + "\"" + input + "\" &"

	ffmenc = "ffmpeg -f yuv4mpegpipe -i " + vfifo + " -i " + afifo + " -acodec libfaac -ac 2 -ab " + str(abitrate) + " -ar 22500 -vcodec libx264 -threads " + str(threads) + " -b " + str(vbitrate) + " -flags +loop -cmp +chroma -partitions +parti4x4+partp8x8+partb8x8 -subq 5 -trellis 1 -refs 1 -coder 0 -me_range 16 -g 300 -keyint_min 25 -sc_threshold 40 -i_qfactor 0.71 -bt 640 -bufsize 10M -rc_eq 'blurCplx^(1-qComp)' -qcomp 0.6 -qmin 10 -qmax 51 -level 30 -f mp4 \"" + output + "\""

	subprocess.Popen(mpvideodec, shell=True, stdout=None, stderr=None)
	subprocess.Popen(mpaudiodec, shell=True, stdout=None, stderr=None)
	subprocess.call(ffmenc, shell=True)

	os.remove(afifo)
	os.remove(vfifo)



def usage():
	"""Print avaiable commandline arguments"""

	print "This is n900-encode.py (C) 2010 Stefan Brand <seiichiro0185 AT tol.ch>"
	print "n900-encode.py usage:\n"
	print "--input <file>    [-i]: Video to Convert"
	print "--output <file>   [-o]: Name of the converted Video"
	print "--mpopts \"<opts>\" [-m]: Additional options for mplayer (eg -sid 1 or -aid 1)"
	print "--abitrate <br>   [-a]: Audio Bitrate in KBit/s"
	print "--vbitrate <br>   [-v]: Video Bitrate in kBit/s"
	print "--threads <num>   [-t]: Use <num> Threads to encode"
	print "--help            [-h]: Print this Help"


# Start the Main Function
if __name__ == "__main__":
    main(sys.argv[1:])
