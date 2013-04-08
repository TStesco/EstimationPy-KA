import numpy as np
import matplotlib.pyplot as plt
from   pylab import figure

import sys
sys.path.insert(0,'./models/stateParamEstimation')
sys.path.insert(0,'./models/stateParamEstimation/plotting')
sys.path.insert(0,'./ukf')

from model import *
from ukf import *
from plotting import *

# time frame of the experiment
dt = 0.02
startTime = 0.0
stopTime  = 30.0
numPoints = int((stopTime - startTime)/dt)
time = np.linspace(startTime, stopTime, numPoints)

# initial state vector (state x, par b)
X0 = np.array([3.5, 5.0])

# output measurement covariance noise
R     = np.array([[0.1**2]])
# input measurement covariance noise
H     = np.array([[0.001*2]])
sqrtH = np.linalg.cholesky(H)

# initial process noise
Q     = np.array([[0.05**2, 0.0],
		  [0.0, 0.2**2]])

# define the model
m = model()
m.setInitialState(X0)
m.setDT(dt)
m.setQ(Q)
m.setR(R)

# input vector
U = np.ones((numPoints,1))
# measured input vector
Um = np.ones((numPoints,1))

# initialize state and output vectors
n_state   = m.getNstates()
n_outputs = m.getNoutputs()

X = np.zeros((numPoints,n_state))
Y = np.zeros((numPoints,n_outputs))
Z = np.zeros((numPoints,n_outputs))

# evolution of the system
for i in range(numPoints):
	if i==0:
		X[i,:] = X0
	else:	
		X[i,:]= m.functionF(X[i-1,:],U[i-1,:],time[i-1])

	Y[i,:]  = m.functionG(X[i,:],U[i,:],time[i])

# noisy measured values
Z  = Y + np.dot(m.sqrtR, np.random.randn(n_outputs,numPoints)).T
Um = U + np.dot(sqrtH, np.random.randn(1,numPoints)).T


########################################################################################
# THE NOISY MEASUREMENTS OF THE OUTPUTS ARE AVAILABLE, START THE FILERING PROCEDURE

# The UKF starts from the guessed initial value Xhat, and a guessed covarance matrix Q
Xhat = np.zeros((numPoints,n_state))
Yhat = np.zeros((numPoints,n_outputs))
P    = np.zeros((numPoints,n_state,n_state))
CovZ = np.zeros((numPoints,n_outputs,n_outputs))

# initial knowledge
X0_hat = np.array([2.5, 2.0])
P0     = Q

# UKF parameters
UKFilter  = ukf(n_state,n_outputs)

# iteration of the UKF
for i in range(numPoints):
	
	if i==0:	
		Xhat[i,:]   = X0_hat
		P[i,:,:]    = P0
		Yhat[i,:]   = m.functionG(Xhat[i,:],U[i,:],time[i])
		CovZ[i,:,:] = m.R
	else:
		Xhat[i,:], P[i,:,:], Yhat[i,:], CovZ[i,:,:] = UKFilter.ukf_step(Z[i],Xhat[i-1,:],P[i-1,:,:],Q,R,Um[i-1,:],Um[i,:],time[i-1],time[i],m,False)

# smoothing the results
Xsmooth = np.zeros((numPoints,n_state))
Psmooth = np.zeros((numPoints,n_state,n_state))

Xsmooth, Psmooth = UKFilter.smooth(time,Xhat,P,Q,Um,m)

# plot the results
plotResults(time,stopTime,X,Y,Z,U,Um,Xhat,Yhat,P,CovZ,Xsmooth,Psmooth)
