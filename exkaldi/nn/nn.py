# coding=utf-8
#
# Yu Wang (University of Yamanashi)
# Mar,2020
#
# Licensed under the Apache License,Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""NN acoustic model training."""

import os
import sys
import random
import subprocess
import tempfile
import numpy as np
import threading
import math
import time
import shutil
from glob import glob

from exkaldi.version import WrongPath,WrongOperation,UnsupportedType,KaldiProcessError
from exkaldi.utils.utils import make_dependent_dirs,type_name,run_shell_command,flatten
from exkaldi.utils import declare
from exkaldi.core.load import load_feat
from collections import namedtuple,Iterable

class Supporter:
	'''
	Supporter is used to manage Neural Network training information.

	Args:
		<outDir>: the output directory of Log information.
	'''      
	def __init__(self,outDir='Result'):
		
		declare.is_valid_dir_name("outDir",outDir)
		make_dependent_dirs(outDir,pathIsFile=False)
		self.outDir = os.path.abspath(outDir)

		self.logFile = os.path.join(self.outDir,'log')
		with open(self.logFile,'w',encoding='utf-8'): pass

		self.currentField = {}
		self.currentFieldIsFloat = {}
		self.globalField = []

		self.lastSavedArch = {}
		self.savedArchs = []
		self.savingThreshold = None

		self._allKeys = []

		self._iterSymbol = -1
		
	def send_report(self,info):
		'''
		Send information and these will be retained untill you do the statistics by using .collect_report().

		Args:
			<info>: a Python dict object includiing names and their values with int or float type.
					such as {"epoch":epoch,"train_loss":loss,"train_acc":acc}
					The value can be Python int,float object,Numpy int,float object or NUmpy ndarray with only one value.
		'''
		declare.is_classes("info",info,dict)

		for name,value in info.items(): 
			assert isinstance(name,str) and len(name) > 0,f"The name of info should be string avaliable but got {type_name(name)}."
			valueDtype = type_name(value)
			if valueDtype.startswith("int"): # Python int object,Numpy int object
				pass

			elif valueDtype.startswith("float"): # Python float object,Numpy float object
				self.currentFieldIsFloat[name] = True
			
			elif valueDtype == "ndarray" and value.shape == ():  # Numpy ndarray with only one value
				if value.dtype == "float":
					self.currentFieldIsFloat[name] = True
			else:
				raise UnsupportedType(f"Expected int or float value but got {type_name(value)}.")

			name = name.lower()
			if not name in self.currentField.keys():
				self.currentField[name] = []
			self.currentField[name].append(value)

	def collect_report(self,keys=None,plot=True):
		'''
		Do the statistics of received information. The result will be saved in outDir/log file. 

		Args:
			<keys>: Specify the data wanted to be collected. If "None",collect all data reported. 
			<plot>: If "True",print the statistics result to standard output.
		'''
		if keys is None:
			keys = list(self.currentField)
		elif isinstance(keys,str):
			keys = [keys,]
		elif isinstance(keys,(list,tuple)):
			pass
		else:
			raise WrongOperation("Expected <keys> is string,list or tuple.")
	
		self.globalField.append({})

		self._allKeys.extend( self.currentField.keys() )
		self._allKeys = list(set(self._allKeys))

		message = ''
		for name in keys:
			if name in self.currentField.keys():

				if len(self.currentField[name]) == 0:
					mn = 0.
				else:
					mn = sum( self.currentField[name] )/len( self.currentField[name] )

				if name in self.currentFieldIsFloat.keys():
					message += f'{name}:{mn:.5f}    '
				else:
					mn = int(mn)
					message += f'{name}:{mn}    '
					
				self.globalField[-1][name] = mn
			else:
				message += f'{name}:-----    '


		with open(self.logFile,'a',encoding='utf-8') as fw:
			fw.write(message + '\n')
		# Print to screen
		if plot is True:
			print(message)
		# Clear
		self.currentField = {}
		self.currentFieldIsFloat = {}

	def save_arch(self,saveFunc,arch,addInfo=None,byKey=None,byMax=True,maxRetain=0):
		'''
		Usage:  obj.save_arch(saveFunc,archs={'model':model,'opt':optimizer})

		Save architecture such as models or optimizers when you use this function.
		Only collected information will be used to check the condition. So data collecting is expected beforehand.

		Args:
			<saveFunc>: a function to save archivements in <arch>. It need a parameter to reseive <arch>,for example:
						When use tensorflow 2.x
							def save_model(arch):
								for fileName,model in arch.items():
									model.save_weights(fileName+".h5")
			<arch>: a dict object whose keys are the name,and values are achivements' object. It will be
			<addInfo>: a reported name. If it is not None,will add the information to saving file name.
			<byKey>: a reported name. If it is not None,save achivements only this value is larger than last saved achivements.
			<byMax>: a bool value. Control the condition of <byKey>.
			<maxRetain>: the max numbers of saved achivements to retain. If 0,retain all.
		''' 
		assert isinstance(arch,dict),"Expected <arch> is dict whose keys are architecture-names and values are architecture-objects."
		declare.is_callable("saveFunc",saveFunc)
		declare.is_non_negative_int("maxRetain",maxRetain)

		#if self.currentField != {}:
		#	self.collect_report(plot=False)
		
		suffix = f"_{self._iterSymbol}"
		self._iterSymbol += 1

		if not addInfo is None:
			assert isinstance(addInfo,(str,list,tuple)),'Expected <addInfo> is string,list or tuple.'
			if isinstance(addInfo,str):
				addInfo = [addInfo,]
			for name in addInfo:
				if not name in self.globalField[-1].keys():
					suffix += f"{name}None"
				else:
					value = self.globalField[-1][name]
					if isinstance(value,float):
						suffix += f"_{name}{value:.4f}".replace(".","")
					else:
						suffix += f"_{name}{value}"

		saveFlag =False

		if byKey is None:
			self.lastSavedArch = {}
			newArchs = {}
			for name in arch.keys():
				fileName = os.path.join(self.outDir,name+suffix)
				newArchs[fileName] = arch[name]
				self.lastSavedArch[name] = fileName
			saveFlag = True

		else:
			byKey = byKey.lower()
			if not byKey in self.globalField[-1].keys():
				print(f"Warning: Failed to save architectures. Because the key {byKey} has not been reported last time.")
				return
			else:
				value = self.globalField[-1][byKey]

			if self.savingThreshold is None:
				self.savingThreshold = value
				save = True
			else:
				if byMax is True and value > self.savingThreshold:
					self.savingThreshold = value
					save = True
				elif byMax is False and value < self.savingThreshold:
					self.savingThreshold = value
					save = True

			if save is True:
				self.lastSavedArch = {}
				for name in arch.keys():
					if (addInfo is None) or (byKey not in addInfo):
						if isinstance(value,float):
							suffix += f"_{name}{value:.4f}".replace(".","")
						else:
							suffix += f"_{name}{value}"
					fileName = os.path.join(self.outDir,name+suffix)
					newArchs[fileName] = arch[name]
					self.lastSavedArch[name] = fileName
		
		if saveFlag is True:
			# Save
			saveFunc(newArchs)
			# Try to correct the file name
			for name,fileName in self.lastSavedArch.items():
				realFileName = glob( fileName + "*" )
				if len(realFileName) == 0:
					raise WrongOperation(f"Achivement whose name starts with {fileName} should have been saved done but not found.")
				elif len(realFileName) > 1:
					raise WrongOperation(f"More than one achivements whose name start with {fileName} were found.")
				else:
					self.lastSavedArch[name] = realFileName[0]

			self.savedArchs.append( self.lastSavedArch.items() )

			for items in self.savedArchs[0:-maxRetain]:
				for name,fileName in items:
					try:
						if os.path.exists(fileName):
							if os.path.isfile(fileName):
								os.remove(fileName)
							elif os.path.isdir(fileName):
								shutil.rmtree(fileName)
							else:
								raise UnsupportedType(f"Failed to remove {fileName}: It is not a file and directory path.")
					except Exception as e:
						print(f"Failed to remove saved achivements:{fileName}.")
						raise e
			
			self.savedArchs = self.savedArchs[-maxRetain:]

	@property
	def finalArch(self):
		'''
		Get the final saved achivements. 
		
		Return:
			A Python dict object whose key is architecture name and value is file path. 
		''' 
		return self.lastSavedArch
   
	def judge(self,key,condition,threshold,byDeltaRatio=False):
		'''
		Usage:  obj.judge('train_loss','<',0.0001,byDeltaRatio=True) or obj.judge('epoch','>=',10)
		
		Check if condition is true. 
		Only collected information will be used to check the condition. So data collecting is expected beforehand.

		Args:
			<key>: the name reported.
			<condition>: a string,condition operators such as ">" or "=="
			<threshold>: a int or float value.
			<byDeltaRatio>: bool value,if true,threshold should be a delta ratio value.
								deltaRatio = abs((value-value_pre)/value) 

		Return:
			True or False. 
		''' 
		declare.is_instance("condition operator",condition,['>','>=','<=','<','==','!='])
		declare.is_classes("threshold",threshold,(int,float))

		#if self.currentField != {}:
		#	self.collect_report(plot=False)
		
		if byDeltaRatio is True:
			p = []
			for i in range(len(self.globalField)-1,-1,-1):
				if key in self.globalField[i].keys():
					p.append(self.globalField[i][key])
				if len(p) == 2:
					value = str(abs((p[0]-p[1])/p[0]))
					return eval( value + condition + str(threshold) )
			return False
		else:
			for i in range(len(self.globalField)-1,-1,-1):
				if key in self.globalField[i].keys():
					value = str(self.globalField[i][key])
					return eval(value + condition + str(threshold))
			return False

	def dump(self,keepItems=False):
		'''
		Usage:  product = obj.dump()
		Get all reported information.

		Args:
			<keepItems>: If True,return a dict object.
						 Else,return a list of dict objects. 
		
		Return:
			A dict object or list object.
		'''
		if self.currentField != {}:
			self.collect_report(plot=False)
		
		if self.globalField != []:
			allData = self.globalField
		else:
			raise WrongOperation('Not any information to dump.')

		if keepItems is True:
			items = {}
			for i in allData:
				for key in i.keys():
					if not key in items.keys():
						items[key] = []
					items[key].append(i[key])
			return items
		else:
			return allData

class DataIterator:

	def __init__(self,indexTable,processFunc,batchSize,chunks='auto',otherArgs=None,shuffle=False,retainData=0.0):
		
		declare.is_index_table("indexTable",indexTable)
		declare.is_callable("processFunc",processFunc)	
		declare.is_positive_int("batchSize",batchSize)
		declare.is_bool("shuffle",shuffle)
		declare.in_boundary("retainData",retainData,minV=0.0,maxV=0.9)

		self.processFunc = processFunc
		self._batchSize = batchSize
		self.otherArgs = otherArgs
		self._shuffle = shuffle
		self._chunks = chunks

		if chunks != 'auto':
			declare.is_positive_int("chunks",chunks)
		
		totalDataNumber = len(indexTable)
		trainDataNumber = int(  totalDataNumber * (1-retainData) )
		evalDataNumber = totalDataNumber - trainDataNumber
		scpTable = indexTable.shuffle()

		self.trainTable = scpTable.subset(nHead=trainDataNumber)
		self.evalTable = scpTable.subset(nTail=evalDataNumber)

		if chunks == 'auto':
			#Compute the chunks automatically
			sampleTable = self.trainTable.subset(nHead=10)
			meanSize = sum([ indexInfo.dataSize for indexInfo in sampleTable.values() ]) / 10
			autoChunkSize = math.ceil(104857600/meanSize)  # 100MB = 102400KB = 104857600 B
			self._chunks = trainDataNumber//autoChunkSize
			if self._chunks == 0: 
				self._chunks = 1

		self.make_dataset_bag(shuffle=False)
		self._epoch = 0
		
		self.load_dataset(0)
		self.currentDataset = self.nextDataset
		self.nextDataset = None

		self.epochSize = len(self.currentDataset)
		self.countEpochSizeFlag = True

		self.currentPosition = 0
		self.currentEpochPosition = 0
		self._isNewEpoch = False
		self._isNewChunk = False
		self.datasetIndex = 0

		if self._chunks > 1:
			self.datasetIndex = 1
			self.loadDatasetThread = threading.Thread(target=self.load_dataset,args=(1,))
			self.loadDatasetThread.start()

	def make_dataset_bag(self,shuffle=False):
		if shuffle:
			self.trainTable.shuffle()
		self.datasetBag = self.trainTable.subset(chunks=self._chunks)

	def load_dataset(self,datasetIndex):
		chunkData = load_feat(self.datasetBag[datasetIndex])
		if self.otherArgs != None:
			self.nextDataset = self.processFunc(self,chunkData,self.otherArgs)
		else:
			self.nextDataset = self.processFunc(self,chunkData)

		assert isinstance(self.nextDataset,Iterable),"Process function should return an iterable objects."
		self.nextDataset = [X for X in self.nextDataset]

		if self._batchSize > len(self.nextDataset):
			print(f"Warning: Batch Size <{self._batchSize}> is extremely large for this dataset,we hope you can use a more suitable value.")
		
	def next(self):
		i = self.currentPosition
		iEnd = i + self._batchSize
		N = len(self.currentDataset)

		batch = self.currentDataset[i:iEnd]

		if self._chunks == 1:
			if iEnd >= N:
				rest = iEnd - N
				if self._shuffle:
					random.shuffle(self.currentDataset)
				batch.extend(self.currentDataset[:rest])
				self.currentPosition = rest
				self.currentEpochPosition = self.currentPosition
				self._epoch += 1
				self._isNewEpoch = True
				self._isNewChunk = True
			else:
				self.currentPosition = iEnd
				self._isNewEpoch = False
				self._isNewChunk = False
		else:
			if iEnd >= N:
				rest = iEnd - N
				if self.loadDatasetThread.is_alive():
					self.loadDatasetThread.join()
				if self._shuffle:
					random.shuffle(self.nextDataset)
				batch.extend(self.nextDataset[:rest])
				self.currentPosition = rest
				self.currentDataset = self.nextDataset
				self._isNewChunk = True
				
				if self.countEpochSizeFlag:
					self.epochSize += len(self.currentDataset)

				self.datasetIndex = (self.datasetIndex+1)%self._chunks

				if self.datasetIndex == 1:
					self._epoch += 1
					self._isNewEpoch = True

				if self.datasetIndex == 0:
					self.countEpochSizeFlag = False
					del self.datasetBag
					self.make_dataset_bag(shuffle=True)

				self.loadDatasetThread = threading.Thread(target=self.load_dataset,args=(self.datasetIndex,))
				self.loadDatasetThread.start()

			else:
				self._isNewChunk = False
				self._isNewEpoch = False
				self.currentPosition = iEnd

			self.currentEpochPosition = (self.currentEpochPosition + self._batchSize)%self.epochSize

		return batch                            

	@property
	def batchSize(self):
		return self._batchSize

	@property
	def chunks(self):
		return self._chunks

	@property
	def chunk(self):
		if self.datasetIndex == 0:
			return self._chunks - 1
		else:
			return self.datasetIndex - 1

	@property
	def epoch(self):
		return self._epoch

	@property
	def isNewEpoch(self):
		return self._isNewEpoch

	@property
	def isNewChunk(self):
		return self._isNewChunk

	@property
	def epochProgress(self):
		if self._isNewEpoch is True:
			return 1.
		else:
			return round(self.currentEpochPosition/self.epochSize,2)
	
	@property
	def chunkProgress(self):
		if self._isNewChunk is True:
			return 1.
		else:
			return round(self.currentPosition/len(self.currentDataset),2)

	def get_retained_data(self,processFunc=None,batchSize=None,chunks='auto',otherArgs=None,shuffle=False,retainData=0.0):

		declare.non_void("retained data",self.evalTable)

		if processFunc is None:
			processFunc = self.processFunc
		
		if batchSize is None:
			batchSize = self._batchSize

		if chunks != 'auto':
			declare.is_positive_int("chunks",chunks)

		if otherArgs is None:
			otherArgs = self.otherArgs

		reIterator = DataIterator(self.evalTable,processFunc,batchSize,chunks,otherArgs,shuffle,retainData)

		return reIterator

def pad_sequence(data,dim=0,maxLength=None,dtype='float32',padding='tail',truncating='tail',value=0.0):
	'''
	Pad sequence.

	Args:
		<data>: a list of NumPy arrays.
		<dim>: which dimmension to pad. All other dimmensions should be the same size.
		<maxLength>: If larger than this theshold,truncate it.
		<dtype>: target dtype.
		<padding>: padding position,"head","tail" or "random".
		<truncating>: truncating position,"head","tail".
		<value>: padding value.
	
	Return:
		a two-tuple: (a Numpy array,a list of padding positions). 
	'''
	declare.is_classes("data",data,(list,tuple))
	declare.is_non_negative_int("dim",dim)
	declare.not_void("data",data)
	declare.is_classes("value",value,(int,float))
	declare.is_instances("padding",padding,["head","tail","random"])
	declare.is_instances("truncating",padding,["head","tail"])
	if maxLength is not None:
		declare.is_positive_int("maxLength",maxLength)

	lengths = []
	newData = []
	exRank = None
	exOtherDims = None
	for i in data:

		# verify
		declare.is_classes("data",i,np.ndarray)
		shape = i.shape
		if exRank is None:
			exRank = len(shape)
			assert dim < exRank,f"<dim> is out of range: {dim}>{exRank-1}."
		else:
			assert len(shape) == exRank,f"Arrays in <data> has different rank: {exRank}!={len(shape)}."

		if dim != 0:
			# transpose
			rank = [r for r in range(exRank)]
			rank[0] = dim
			rank[dim] = 0
			i = i.transpose(rank)

		if exOtherDims is None:
			exOtherDims = i.shape[1:]
		else:
			assert exOtherDims == i.shape[1:],f"Expect for sequential dimmension,All arrays in <data> has same shape but got: {exOtherDims}!={i.shape[1:]}."

		length = len(i)
		if maxLength is not None and length > maxLength:
			if truncating == "head":
				i = i[maxLength:,...]
			else:
				i = i[0:maxLength:,...]

		lengths.append(len(i))
		newData.append(i)

	maxLength = max(lengths)
	batchSize = len(newData)

	result = np.array(value,dtype=dtype) * np.ones([batchSize,maxLength,*exOtherDims],dtype=dtype)

	pos = []
	for i in range(batchSize):
		length = lengths[i]
		if padding == "tail":
			result[i][0:length] = newData[i]
			pos.append((0,length))
		elif padding == "head":
			start = maxLength - length
			result[i][start:] = newData[i]
			pos.append((start,maxLength))
		else:
			start = random.randint(0,maxLength-length)
			end = start + length
			result[i][start:end] = newData[i]
			pos.append((start,end))

	if dim != 0:
		exRank = len(result.shape)
		rank = [r for r in range(exRank)]
		rank[1] = dim+1
		rank[dim+1] = 1
		result = result.transpose(rank)

	return result,pos

def softmax(data,axis=1):
	'''
	The softmax function.

	Args:
		<data>: a Numpy array.
		<axis>: the dimension to softmax.
		
	Return:
		A new array.
	'''
	declare.is_classes("data",data,np.ndarray)
	if len(data.shape) == 1:
		axis = 0
	declare.in_boundary("axis",axis,0,len(data.shape)-1 )
	
	maxValue = data.max(axis,keepdims=True)
	dataNor = data - maxValue

	dataExp = np.exp(dataNor)
	dataExpSum = np.sum(dataExp,axis,keepdims = True)

	return dataExp / dataExpSum

def log_softmax(data,axis=1):
	'''
	The log-softmax function.

	Args:
		<data>: a Numpy array.
		<axis>: the dimension to softmax.
	Return:
		A new array.
	'''
	declare.is_classes("data",data,np.ndarray)
	if len(data.shape) == 1:
		axis = 0
	declare.in_boundary("axis",axis,0,len(data.shape)-1 )

	dataShape = list(data.shape)
	dataShape[axis] = 1
	maxValue = data.max(axis,keepdims=True)
	dataNor = data - maxValue
	
	dataExp = np.exp(dataNor)
	dataExpSum = np.sum(dataExp,axis)
	dataExpSumLog = np.log(dataExpSum) + maxValue.reshape(dataExpSum.shape)
	
	return data - dataExpSumLog.reshape(dataShape)

def accuracy(ref,hyp,ignore=None,mode='all'):
	'''
	Score one-2-one matching score between two items.

	Args:
		<ref>,<hyp>: iterable objects like list,tuple or NumPy array. It will be flattened before scoring.
		<ignore>: Ignoring specific symbols.
		<model>: If <mode> is "all",compute one-one matching score. For example,<ref> is (1,2,3,4),and <hyp> is (1,2,2,4),the score will be 0.75.
				 If <mode> is "present",only the members of <hyp> which appeared in <ref> will be scored no matter which position it is. 
	Return:
		a namedtuple object of score information.
	'''
	assert type_name(ref)!="Transcription" and type_name(hyp) != "Transcription","Exkaldi Transcription objects are unsupported in this function."

	assert mode in ['all','present'],'Expected <mode> to be "present" or "all".'

	x = flatten(ref)
	x = list( filter(lambda i:i!=ignore,x) ) 
	y = flatten(hyp)
	y = list( filter(lambda i:i!=ignore,y) ) 

	if mode == 'all':
		i = 0
		score = 0
		while True:
			if i >= len(x) or i >= len(y):
				break
			elif x[i] == y[i]:
				score += 1
			i += 1
		if i < len(x) or i < len(y):
			raise WrongOperation('<ref> and <hyp> have different length to score.')
		else:
			if len(x) == 0:
				accuracy = 1.0
			else:
				accuracy = score/len(x)

			return namedtuple("Score",["accuracy","items","rightItems"])(
						accuracy,len(x),score
					)
	else:
		x = sorted(x)
		score = 0
		for i in y:
			if i in x:
				score += 1
		if len(y) == 0:
			if len(x) == 0:
				accuracy = 1.0
			else:
				accuracy = 0.0
		else:
			accuracy = score/len(y)
		
		return namedtuple("Score",["accuracy","items","rightItems"])(
					accuracy,len(y),score
				)

def pure_edit_distance(ref,hyp,ignore=None):
	'''
	Compute edit-distance score.

	Args:
		<ref>,<hyp>: iterable objects like list,tuple or NumPy array. It will be flattened before scoring.
		<ignore>: Ignoring specific symbols.	 
	Return:
		a namedtuple object including score information.	
	'''
	assert isinstance(ref,Iterable),"<ref> is not a iterable object."
	assert isinstance(hyp,Iterable),"<hyp> is not a iterable object."
	
	x = flatten(ref)
	x = list( filter(lambda i:i!=ignore,x) ) 
	y = flatten(hyp)
	y = list( filter(lambda i:i!=ignore,y) ) 

	lenX = len(x)
	lenY = len(y)

	mapping = np.zeros((lenX+1,lenY+1))

	for i in range(lenX+1):
		mapping[i][0] = i
	for j in range(lenY+1):
		mapping[0][j] = j
	for i in range(1,lenX+1):
		for j in range(1,lenY+1):
			if x[i-1] == y[j-1]:
				delta = 0
			else:
				delta = 1       
			mapping[i][j] = min(mapping[i-1][j-1]+delta,min(mapping[i-1][j]+1,mapping[i][j-1]+1))
	
	score = int(mapping[lenX][lenY])
	return namedtuple("Score",["editDistance","items"])(
				score,len(x)
			)

def compute_postprob_norm(ali,probDims):
	'''
	Compute alignment counts in order to normalize acoustic model posterior probability.
	For more help information,look at the Kaldi <analyze-counts> command.

	Args:
		<ali>: exkaldi NumpyAlignmentTrans,NumpyAlignmentPhone or NumpyAlignmentPdf object.
		<probDims>: the dimensionality of posterior probability.
		
	Return:
		A numpy array of the normalization.
	''' 
	declare.kaldi_existed()
	declare.is_classes("ali",ali,["NumpyAlignmentTrans","NumpyAlignmentPhone","NumpyAlignmentPdf"])
	declare.is_positive_int("probDims",probDims)

	txt = []
	for key,vlaue in ali.items():
		value = " ".join(map(str,vlaue.tolist()))
		txt.append( key+" "+value )
	txt = "\n".join(txt)

	cmd = f"analyze-counts --binary=false --counts-dim={probDims} ark:- -"
	out,err,cod = run_shell_command(cmd,stdin="PIPE",stdout="PIPE",stderr="PIPE",inputs=txt)
	if (isinstance(cod,int) and cod != 0) or out == b"":
		print(err.decode())
		raise KaldiProcessError('Analyze counts defailed.')
	else:
		out = out.decode().strip().strip("[]").strip().split()
		counts = np.array(out,dtype=np.float32)
		countBias = np.log(counts/np.sum(counts))
		return countBias