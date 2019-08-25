# PythonKaldi
This is a tool which introduce kaldi tools into python in a easy-use way.

## PythonKaldi at a Glance

1. Clone the PythonKaldi project.
```
git clone https://github.com/wangyu09/pythonkaldi
```

2. In the file < CSJsample.py >, there is a sample program that showed how to use the PythonKaldi tool. Exchange the parameter < CSJpath > for yours and also other parameters such as < epoch > if you want. Then run it.
```
python CSJsample.py
```
Especially, there are three sections in this sample program: first, train chainer neural network as acoustic model, and then use this pretrained AM to forward test data and decode them by generating lattice and further compute the WER. In the third step function < OnlineRecognize >, although we wrote it, I am sorry that it cannot be used now because of debugging.

## Concepts and Usage
Most of functions in PythonKaldi tool are performed with using "subprocess" to run shell cmd of kaldi tools. But we design a series of classes and functions to use them in a flexible way and it is more familiar for python programmer. PythonKaldi tool consist of three parts: < Basis Tools > to cover kaldi functions, < Speek client > to realize online-recognization, and < Chainer Tools > to give some useful tools to help train neural network acoustic model.


_-----------------------------------------------< Basis Tools >-----------------------------------------------------_
### KaldiArk   

<basic class>  

**KaldiArk** is a subclass of **bytes**. It maks a object who holds the kaldi ark data in a binary type. **KaldiArk** and **KaldiDict** object have almost the same attributes and functions, and they can do some mixed operations such as "+" and "concat" and so on.  
Moreover, alignment can also be held by KaldiArk and KaldiDict in Pythonkaldi tool, and we defined it as int32 data type.  

< Attributes >  

`.lens`   
return a tuple: ( the numbers of all utterances, the frames of each utterance ).  

`.dim`    
return a int: feature dim.  

`.dtype`    
return a str: data type such as 'float32'.  

`.utts`    
return a list: all utterance names.  

`.array`    
return a KaldiDict object: transform binary ark data into numpy arrar format.  

< Methods >    

`.toDtype(dtype)`    
change data dtype and return.  

`.check_format()`    
check if inner data has a correct kaldi ark format. If had, return True.  

`.save(fileName,chunks=1)`   
save as .ark file. If chunks>1, split it averagely and save them.  

`+ operator` 
KaldiArk object can use < + > operator with another KaldiArk object or KaldiDict object.  

`.concat(others,axis=1)`  
Return KaldiArk object. If any member has a dtype of float, the result will be float, or it will be int.  
It only return the concat results whose utterance id appeared in all members at the same time.

`.splice(left,right=None)`  
Return KaldiArk object. Splice front-behind frames. if right == None, we use right = left.  

`.subset(nHead=0,chunks=1,uttList=None)`  
if nhead > 0, return KaldiArk object which only has start nHead utterances.  
if chunks > 1, return list whose members are KaldiArk.  
if uttList != None, select utterances if utterance id appeared.  

### KaldiDict 

<basic class>  

**KaldiDict** is a subclass of **dict**. It is a object who holds the kaldi ark data in numpy array type. Its key are the utterance id and the value is the numpy array data. **KaldiDict** can also do some mixed operations with **KaldiArk** such as "+" and "concat" and so on.  
Note that **KaldiDict** has some functions which **KaldiArk** dosen't have. They will be introduced as follow.

< Attributes >  

`.lens`    
the same as **KaldiArk**.lens

`.dim`   
the same as **KaldiArk**.dim

`.dtype`    
the same as **KaldiArk**.dtype

`.utts`   
the same as **KaldiArk**.utts

`.array`   
return a KaldiArk object: transform numpy array data into kaldi binary format.  

< Methods >    

`.toDtype(dtype)`    
the same as **KaldiArk**.toDtype

`.check_format()`    
the same as **KaldiArk**.check_format

`.save(fileName,chunks=1)`  
the same as **KaldiArk**.save 

`+ operator`  
the same as **KaldiArk**.add. KaldiDict object can also use < + > operator with another KaldiArk object.    

`.concat(others,axis=1)`    
the same as **KaldiArk**.concat  

`.splice(left,right=None)`    
the same as **KaldiArk**.splice  

`.subset(nHead=0,chunks=1,uttList=None)`    
the same as **KaldiArk**.subset  

`.merge(keepDim=False)`    
return a tuple. if keepDim == True the first member is list whose content are numpy arrays of all utterances, and if keepDim == False, it is a integrated numpy array of all utterances. the second member is utterance ids and their frame length information. 

`.remerge(matrix,uttLens)`    
if self has not any data, do not return, or return a new KaldiDict object. this is a inverse operation of .merge function.

`.normalize(std=True,alpha=1.0,beta=0.0,epsilon=1e-6,axis=0)`    
return a KaldiDict object. if std == True, do _alpha*(x-mean)/(std+epsilon)+belta_, or do _alpha*(x-mean)+belta_.

### KaldiLattice 

<basic class>

**KaldiLattice** holds the lattice and its related file path: HmmGmm file and WordSymbol file. PythonKaldi.decode_lattice function will return a KaldiLattice object. Aslo, you can define a empty KaldiLattice object and load its data later.


< Attributes >  

`.value`    
return a lattice with a binary data type.

< Methods >  

`.load(latFile,HmmGmm,wordSymbol)`        
load lattice. < latFile > can be file path or binary data. < HmmGmm > and < wordSymbol > are expected as file path.

`.get_1best_words(minLmwt=1,maxLmwt=None,Acwt=1.0,outDir='.',asFile=False)`   
return dict object. key is the lmwt value. if < asFile > == True or file name, the result will be save as file and values of returned dict is these files' path, or they will be 1-best words.

`.scale(Acwt=1,inAcwt=1,Ac2Lm=0,Lmwt=1,Lm2Ac=0)`  
return a new scaled KaldiLattice object.

`.add_penalty(penalty=0)`  
return a new KaldiLattice object.

`.save(fileName)`  
save lattice as .gz file.

`+ operator`  
add the numbers of lattice. Note that it is just a simple addtional operation.

### compute_mfcc(wavFile,_**other parameters_)

<function>

compute mfcc feature. return KaldiArk object or file path.  

< Parameters >  

`wavFile`   _wav file or scp file, you can declare its type by using point useSuffix_  
`rate`   _sample rate, default = 16000_  
`frameWidth`   _stride windows width, milliseconds, default = 25_  
`frameShift`   _stride windows width, milliseconds, default = 10_  
`melBins`   _numbers of mel bins, default = 23_  
`featDim`   _dimendionality of mfcc feature, default = 13_  
`windowType`   _window function, default = 'povey'_  
`useUtt`   _when file is a wave file, you can name its utterance id, default = "MAIN"_  
`useSuffix`   _when file is a scp file but withou 'scp' suffix, you can declare its file suffix, default = None_  
`configFile`   _It is unable now and must be None_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  
`wavFile` _wav file or scp file, you can declare its type by using <useSuffix>_  
  
### compute_fbank(wavFile,_**other parameters_)

<function>

compute fbank feature. return KaldiArk object or file path.  

< Parameters >  

`wavFile`   _wav file or scp file, you can declare its type by using point useSuffix_  
`rate`   _sample rate, default = 16000_  
`frameWidth`   _stride windows width, milliseconds, default = 25_  
`frameShift`   _stride windows width, milliseconds, default = 10_  
`melBins`   _numbers of mel bins, default = 23_  
`windowType`   _window function, default = 'povey'_  
`useUtt`   _when file is a wave file, you can name its utterance id, default = "MAIN"_  
`useSuffix`   _when file is a scp file but withou 'scp' suffix, you can declare its file suffix, default = None_  
`configFile`   _It is unable now and must be None_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  

### compute_plp(wavFile,_**other parameters_)  

<function>

compute plp feature. return KaldiArk object or file path.  

< Parameters >  

`wavFile`   _wav file or scp file, you can declare its type by using point useSuffix_  
`rate`   _sample rate, default = 16000_  
`frameWidth`   _stride windows width, milliseconds, default = 25_  
`frameShift`   _stride windows width, milliseconds, default = 10_  
`melBins`   _numbers of mel bins, default = 23_  
`featDim`   _dimendionality of mfcc feature, default = 13_  
`windowType`   _window function, default = 'povey'_  
`useUtt`   _when file is a wave file, you can name its utterance id, default = "MAIN"_  
`useSuffix`   _when file is a scp file but withou 'scp' suffix, you can declare its file suffix, default = None_  
`configFile`   _It is unable now and must be None_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  

### compute_spectrogram(wavFile,_**other parameters_) 

<function>

compute spectrogram feature. return KaldiArk object or file path.  

< Parameters >  

`wavFile`   _wav file or scp file, you can declare its type by using point useSuffix_  
`rate`   _sample rate, default = 16000_  
`frameWidth`   _stride windows width, milliseconds, default = 25_  
`frameShift`   _stride windows width, milliseconds, default = 10_  
`windowType`   _window function, default = 'povey'_  
`useUtt`   _when file is a wave file, you can name its utterance id, default = "MAIN"_  
`useSuffix`   _when file is a scp file but withou 'scp' suffix, you can declare its file suffix, default = None_  
`configFile`   _It is unable now and must be None_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  

### use_cmvn(feat,_**other parameters_) 

< function >

apply CMVN to feature. return KaldiArk object or file path.
if all of other parameters are None, compute the CMVN state within each utterance firstly and use them.

< Parameters >  

`feat` _KaldiArk or KaldiDict object_
`cmvnStatFile`   _if None compute it firstly, default = None_  
`spk2uttFile`   _if None compute cmvn state whin each utterance, default = None_  
`spk2uttFile`   _if None and spk2uttFile != None, raise error, default = None_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  

### use_cmvn_sliding(feat,_**other parameters_) 

< function >

apply sliding CMVN to feature. return KaldiArk object or file path.

< Parameters >  

`feat` _KaldiArk or KaldiDict object_
`windowsSize`   _sliding windows width, frames, if None, set it to cover all frames at one time, default = None_  
`std`   _if False, only apply mean, default = False_ 

### add_delta(feat,_**other parameters_) 

< function >

add n orders delta to feature. return KaldiArk object or file path.

< Parameters >  

`feat` _KaldiArk or KaldiDict object_
`order`   _the times of delta, default = 2_ 
`asFile`   _if True or file name, save result as file and return file path, or return KaldiArk, default = False_  

### get_ali(faliFile,HmmGmm,_**other parameters_) 

< function >

get alignment from alignment file. return KaldiDict object.

< Parameters >  

`faliFile` _kaldi alignment file path_
`HmmGmm`   _HmmGmm model path_ 
`returnPhoneme`   _if True, return phoneme id, or return pdf id, default = False_

### decompress(data) 

< function >

decompress kaldi compressed feature data. return KaldiArk object.

< Parameters >  

`data` _the binary data of kaldi compressed feature_

### load(filePath,_**other parameters_) 

< function >

load kaldi ark feat file, kaldi scp feat file, KaldiArk file, or KaldiDict file. return KaldiArk or KaldiDict object.

< Parameters >  

`filePath` _file path with a suffix '.ark' or '.scp' or '.npy'_
`useSuffix`   _when file has another suffix, you can declare it, default = None_

### decode_lattice(AmP,HmmGmm,Hclg,Lexicon,_**other parameters_) 

< function >

decode by generating lattice. return KaldiLattice object.

< Parameters >  

`AmP` _acoustic model loglike probability, KaldiArk object_  
`HmmGmm`   _HmmGmm file path_  
`Hclg`   _Hclg file path_  
`Lexicon`   _word symbol file path_  
`minActive`   _minimum active, default=200_  
`maxMem`   _maximum memory, default=50000000_  
`maxActive`   _maximum active, default=7000_  
`beam`   _beam, default=13_
`latBeam`   _lattice beam, default=8_
`Acwt`   _acoustic model weight, default=1_
`configFile`   _it is unable to use and must be None_  
`maxThreads`   _the numbers of decode thread, default=1_  
`asFile`   _if True or file name, save result as file and return file path, or return KaldiLattice object, default = False_  
### run_shell_cmd(cmd,_**other parameters_) 

< function >

provide a basic way to run shell command. return (out,err).

< Parameters >  

`cmd` _shell command, string_  
`inputs`   _inputs data, string, default=None_  

### compute_wer(hyp,ref,_**other parameters_) 

< function >

compute wer between prediction result and reference text. return a dict object with score information like {'WER':0,'allWords':10,'ins':0,'del':0,'sub':0,'SER':0,'wrongSentences':0,'allSentences':1,'missedSentences':0}

< Parameters >  

`hyp` _prediction result file or result-list which obtained from KaldiLattice.get_1best_words function_     
`ref` _reference text file or result-like-list_   
`mode` _score mode, default=present_
`ignore` _ignore some symbol such as "sil" before score, default=None_
`p` _if True, score quietly without any print information, default=True_

### split_file(filePath,_**other parameters_) 

< function >

split a large scp file into n smaller files. return a list whose members are splited files' path.

< Parameters >  

`filePath` _scp file path_     
`chunks` _expected numbers, must >1, default=2_   

_-----------------------------------------------< Speak Client >-----------------------------------------------------_

### SpeakClient

< class >

I am sorry it is unable to use for the moment.

### RemoteServer

< class >

I am sorry it is unable to use for the moment.


_-----------------------------------------------< Chainer Tools >-----------------------------------------------------_

### check_model_config  

< function >  

we prepared two kinds of model: MLP and LSTM. return a dict object consisting of model configure.  

< Parameters >  

`modelName` _if modelName="MLP" or "LSTM", it will return necessary configure keys and default value, default=None_
`configFile` _i am sorry it is unable to use at the moment, it must be None, default=None_

### MLP

< class >

chainer MLP model. use `model=MLP(config=config)` to introduce configure and get MLP model. if config == None, the default configure will be use. you can use `print(model)` to watch the architecture of model.

### LSTM

< class >

chainer LSTM model. the same as MLP.

### DataIterator

< class >

you can use it as ordinary chainer.iterators.SerialIterator, but you can also try its distinctive ability. if you give it a large scp file of train data, it will split it into n smaller chunks and load them into momery alternately with parallel thread. it will shuffle all data while is new epoch.

< init Parameters >

`dataOrScpFiles` _ordinary data type or scp file, if scp file, processFunc is necessary._  
`batchSize` _mini batch size_  
`chunks` _if scp file, split it into n chunks. if chunks=='auto', compute the chunks automatically. default="auto"_  
`processFunc` _a function to process scp file to ordinary data type_  
`shuffle` _shuffle batch data, default=True_  
`labelOrAliFiles` _if not None, alignment file or labels will be splited into n chunks and give them to processFunc,default=None_  
`hmmGmm` _if None, will find model automatically according to aliFile, default=None_  
`validDataRatio` _if > 0 , will reserve a part of data as valid data, default=0.1_  

### Supporter

< class >

a class such as chainer report. But we designed some useful functions such as save model by maximum accuracy and adjust learning rate. 

< init Parameters >

`outDir` _out floder, model and log will be saved here, default="Result"_

< Attributes >

`finalModel`   
_return the last saved model path_  

< Methods >

`send_report(x)`   
send information which has a format such as {"epoch":epoch,"train_loss":loss} to supporter object.

`collect_report(keys=None,plot=True)`   
do the statistics of received information. if keys != None, only collect the data in keys. if plot == True, print the statistics result to standard output.

`save_model(self,models,iterSymbol=None,byKey=None,maxValue=True,saveFunc=None)`   
do the statistics of received information. if keys != None, only collect the data in keys. if plot == True, print the statistics result to standard output.






