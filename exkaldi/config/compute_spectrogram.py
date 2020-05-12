compute_spectrogram =  {
                "--allow-downsample":["false",str],
				"--allow-upsample":["false",str],
				"--blackman-coeff":[0.42,float],
				"--channel":[-1,int],
				"--dither":[1,int],
				"--energy-floor":[0,int],
				"--frame-length":[25,int],
				"--frame-shift":[10,int],
				"--max-feature-vectors":[-1,int],
				"--min-duration":[0,int],
				"--output-format":["kaldi",str],
				"--preemphasis-coefficient":[0.97,float],
				"--raw-energy":["true",str],
				"--remove-dc-offset":["true",str],
				"--round-to-power-of-two":["true",str],
				"--sample-frequency":[16000,int],
				"--snip-edges":["false",str],
				"--subtract-mean":["false",str],
				"--window-type":["povey",str],
				"--write-utt2dur":["",str]
			} 