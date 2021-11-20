// TODO: WebkitURL is deprecated.
URL = window.URL || window.webkitURL;

// Stream from getUserMedia()
var gumStream;
// Recorder.js object
var rec = null;
// MediaStreamAudioSourceNode we'll be recording
var input;

// shim for AudioContext when it's not avb. 
var AudioContext = window.AudioContext || window.webkitAudioContext;
var audioContext //audio context to help us record

var recordButton = document.getElementById("recordButton");
var stopButton = document.getElementById("stopButton");
var pauseButton = document.getElementById("pauseButton");

//add events to those 2 buttons
recordButton.addEventListener("click", startRecording);
stopButton.addEventListener("click", stopRecording);
pauseButton.addEventListener("click", pauseRecording);

function activateButtons() {
	recordButton.style.display = stopButton.style.display = pauseButton.style.display = 'block';
	document.getElementById("timer").style.display = 'block';

	let data = new FormData();
	data.append('json', JSON.stringify({'type' : 'access'}));

	fetch('/cmd', {
		method: 'POST',
		body: data
	})
	.then((response) => response.blob())
	.then((blob) => {
		createInvisibleAudio(blob, true);
	}).catch((err) => {
		console.error(err);
		alert('An error occurred, please try again later!');
	});
}

var minutesLabel = document.getElementById("recording-minutes");
var secondsLabel = document.getElementById("recording-seconds");
var start_ = null;
var pause_ = null;
var total_pause_ = 0;

function enable() {
  console.log("Recording started!");

  // Reset the parameters.
  start_ = + new Date(), total_pause_ = 0;

  // Nyquist frequency.
  setInterval(setTime, 500);

  // And start recording.
  rec.record();
}

function pause() {
  pause_ = + new Date();
  rec.stop();
}

function resume() {
  total_pause_ += (+ new Date() - pause_);
  rec.record();
}

function stop() {
  rec.stop();
}

function setTime() {
  // Skip.
  if ((!rec) || (!rec.recording)) return;

  let totalSeconds = parseInt(((+ new Date() - start_) - total_pause_) / 1000);
  secondsLabel.innerHTML = pad(totalSeconds % 60);
  minutesLabel.innerHTML = pad(parseInt(totalSeconds / 60));
}

function pad(val) {
  var valString = val + "";
  if (valString.length < 2) {
    return "0" + valString;
  } else {
    return valString;
  }
}

function startRecording() {
	console.log("recordButton clicked");

	/*
		Simple constraints object, for more advanced audio features see
		https://addpipe.com/blog/audio-constraints-getusermedia/
	*/
    
    var constraints = { audio: true, video:false }

 	/*
    	Disable the record button until we get a success or fail from getUserMedia() 
	*/

	recordButton.disabled = true;
	stopButton.disabled = false;
	pauseButton.disabled = false

	/*
    	We're using the standard promise based getUserMedia() 
    	https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
	*/

	navigator.mediaDevices.getUserMedia(constraints).then(function(stream) {
		console.log("getUserMedia() success, stream created, initializing Recorder.js ...");

		/*
			create an audio context after getUserMedia is called
			sampleRate might change after getUserMedia is called, like it does on macOS when recording through AirPods
			the sampleRate defaults to the one set in your OS for your playback device

		*/
		audioContext = new AudioContext();

		//update the format 
		//document.getElementById("formats").innerHTML="Format: 1 channel pcm @ "+audioContext.sampleRate/1000+"kHz"

		/*  assign to gumStream for later use  */
		gumStream = stream;
		
		/* use the stream */
		input = audioContext.createMediaStreamSource(stream);

		/* 
			Create the Recorder object and configure to record mono sound (1 channel)
			Recording 2 channels  will double the file size
		*/
		rec = new Recorder(input,{numChannels:1})

		// Enable recording.
    enable();
	}).catch(function(err) {
			console.log("in catch!");
	  	// Enable the record button if getUserMedia() fails
    	recordButton.disabled = false;
    	stopButton.disabled = true;
    	pauseButton.disabled = true
	});
}

function pauseRecording(){
  console.log("pauseButton clicked rec.recording=",rec.recording );
	if (rec.recording) {
    pause();
		pauseButton.innerHTML = `Resume`;
	} else {
    resume();
		pauseButton.innerHTML = `Pause`;
	}
}

function stopRecording() {
	console.log("stopButton clicked");

	// Disable the stop button, enable the record too allow for new recordings
	stopButton.disabled = true;
	recordButton.disabled = false;
	pauseButton.disabled = true;

	// Reset button just in case the recording is stopped while paused
	pauseButton.innerHTML = "Pause";
	
	// Tell the recorder to stop the recording
  stop();

	// Stop microphone access
	gumStream.getAudioTracks()[0].stop();

	// Create the wav blob and pass it on to createDownloadLink
	rec.exportWAV(sendBlob);
}

function createInvisibleAudio(blob, shouldAutoPlay=false) {
	var url = URL.createObjectURL(blob);
  var au = document.createElement('audio');
	if (shouldAutoPlay)
		au.autoplay = true;
	au.display = "none";
	au.controls = true;
	au.src = url;
}

function sendBlob(blob) {
	console.log("enters sendBlob")

	const formData = new FormData();
	formData.append('audio', blob, 'recording');
	fetch('/record', {
		method: 'POST',
		body: formData,
	})
	.then((response) => response.blob())
	.then((blob) => {
		createInvisibleAudio(blob, true);
	}).catch((err) => {
		console.error(err);
		alert('An error occurred, please try again later!');
	});
}

async function uploadRecordingToStorage(blob, filename) {
  return storage.ref('recordings').child(filename).put(blob);
}

function createDownloadLink(blob) {
  console.log(blob);

	var url = URL.createObjectURL(blob);
  console.log(url);
	var au = document.createElement('audio');
	au.autoplay=true;
	au.display = "none";
	var li = document.createElement('li');
	var link = document.createElement('a');

  // // Get a key for a new invoice.
  // let newRecordingKey = firebase.database().ref().child('recordings').push().key;
  // let filename = `recording-${newRecordingKey}`;

  // uploadRecordingToStorage()

  // // And update.
  // let updates = {};
  // updates['/recordings/' + newRecordingKey] = invoiceData;
  //  [newInvoiceKey, pdfName, db.ref().update(updates)];

  let filename = 'recording';

	// //add controls to the <audio> element
	au.controls = true;
	au.src = url;

	//save to disk link
	link.href = url;
	link.download = filename + ".wav"; //download forces the browser to donwload the file using the  filename
	link.innerHTML = "Save to disk";

	//add the new audio element to li
	li.appendChild(au);
	
	//add the filename to the li
	li.appendChild(document.createTextNode(filename + ".wav "))

	//add the save to disk link to li
	li.appendChild(link);
  
  //upload link
  var upload = document.createElement('a');
  upload.href="#";
  upload.innerHTML = "Upload";
/*
  upload.addEventListener("click", e => {
    e.preventDefault();
		e.stopPropagation();

		// Reset the tone.
		// TODO: save it to the right of the saved recording!
		document.getElementById('tone').innerHTML = ``;
      
    const formData = new FormData();
    formData.append('audio', blob, 'recording');
    fetch('/record', {
      method: 'POST',
      body: formData,
    })
    .then((response) => response.json())
    .then((data) => {
      console.log(data);
      document.getElementById('tone').innerHTML = data['tone'];
    }).catch((err) => {
      console.error(err);
      alert('An error occurred, please try again later!');
    });
  });*/
	
  li.appendChild(document.createTextNode (" "))//add a space in between
	li.appendChild(upload)//add the upload link to li

	//add the li element to the ol
	recordingsList.appendChild(li);
}
