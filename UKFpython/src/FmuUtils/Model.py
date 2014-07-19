'''
Created on Sep 6, 2013

@author: marco
'''

import pyfmi
import numpy
import pandas as pd
import Strings
import datetime

from FmuUtils.InOutVar import InOutVar
from FmuUtils.Tree import Tree
from FmuUtils.EstimationVariable import EstimationVariable

class Model():
    """
    
    This class contains a reference to a particular FMU that has been loaded into the tool.
    For this FMU, several information are collected together. These information describe what to do with the FMU in 
    the future steps.
    
    A list of:
    
    - parameters,
    - and state variables
    
    that will be estimated/identified.
    
    A list of:
    
    - inputs data series,
    - and output data series
    
    that will be used for simulating the FMU and comparing results.
    
    """
    
    def __init__(self, fmuFile = None, result_handler = None, solver = None, atol = 1e-6, rtol = 1e-4, setTrees = False, verbose = None):
        """
        
        Constructor of the class Model.
        
        """
        
        # Reference to the FMU, that will be loaded using pyfmi
        self.fmu = None
        self.fmuFile = fmuFile
        # List of parameters
        self.parameters = []
        # List of state variables
        self.variables = []
        # List of inputs
        self.inputs = []
        # List of outputs
        self.outputs = []
        
        # Initialize the properties of the FMU
        self.name = ""
        self.author = ""
        self.description = ""
        self.type = ""
        self.version = ""
        self.guid = ""
        self.tool = ""
        self.numStates = ""
        
        # Trees that describe parameters, state variables, inputs and outputs hierarchy
        self.treeParameters = Tree(Strings.PARAMETER_STRING)
        self.treeVariables = Tree(Strings.VARIABLE_STRING)
        self.treeInputs = Tree(Strings.INPUT_STRING)
        self.treeOutputs = Tree(Strings.OUTPUT_STRING)
        
        # Number of maximum tries for a simulation to be successfully run
        self.SIMULATION_TRIES = 4
        
        # Empty dictionary that will contain the simulation options
        self.opts = {}
        
        # Set the number of states
        self.N_STATES = 0
        
        # An array that contains the value references for every state variable
        self.StateValueReferences = []
        
        # See what can be done in catching the exception/propagating it
        if fmuFile != None:
            self.__SetFMU(fmuFile, result_handler, solver, atol, rtol, verbose)
            if setTrees:
                self.__SetTrees()
    
    def AddParameter(self, obj):
        """
        This method add one object to the list of parameters. This list contains only the parameters that 
        will be modified during the further analysis
        """
        if self.IsParameterPresent(obj):
            print "Parameter: ", obj, " not added, already present"
            return False
        else:
            # the object is not yet part of the list, add it            
            par = EstimationVariable(obj, self)
            self.parameters.append(par)
            print "Added variable: ",obj," (",par,")"
            
            return True
    
    def AddVariable(self, obj):
        """
        This method add one object to the list of variables. This list contains only the variables that 
        will be modified during the further analysis
        """
        if self.IsVariablePresent(obj):
            print "Variable: ", obj, " not added, already present"
            return False
        else:
            # the object is not yet part of the list, add it
            # but before embed it into an EstimationVariable class
            var = EstimationVariable(obj, self)
            self.variables.append(var)
            print "Added variable: ",obj," (",var,")"
            return True
    
    def CheckInputData(self, align = True):
        """
        This method check if all the input data are ready to be used or not. If not because they are not aligned, this method
        tries to correct them providing an interpolation
        """
        return self.CheckDataList(self.inputs, align)
    
    def CheckDataList(self, dataList, align = True):
        """
        This method check if all the data series provided by the dataList are ready to be used or not.
        If not because they are not aligned, this method tries to correct them providing an interpolation
        """
        # TODO: Done
        
        # Create a list of data series, one for each input
        dataSeries = []
        for inp in dataList:
            dataSeries.append(inp.GetDataSeries())
        
        Ninputs = len(dataSeries)
        Tmin = 0.0
        Tmax = 0.0
        Npoints = 0
        match = True
        
        # Scan all the data series
        for i in range(Ninputs):
            
            if i == 0:
                Tmin = dataSeries[i].index[0]
                Tmax = dataSeries[i].index[-1]
            else:
                if not dataSeries[i].index.tolist() == dataSeries[i-1].index.tolist():
                    match = False
                    Tmin = max(Tmin, dataSeries[i].index[0])
                    Tmax = min(Tmax, dataSeries[i].index[-1])
        
        # Check if they match or not           
        if match == False and align:
            
            # At the end of this loop we know
            # which data series has the bigger number of points and will
            # be used as base for the other ones
            MaxPoints = 0
            ind = 0
            for i in range(Ninputs):
                NumP = len(dataSeries[i].ix[0])
                if NumP > MaxPoints:
                    MaxPoints = NumP
                    ind = i
            
            # Select the best index
            new_index = dataSeries[ind].index
            
            # Interpolate using the same datetimeIndex
            for inp in dataList:
                inp.GetDataSeries().reindex(new_index).interpolate(method='linear')
                
            return False
        else:
            print "\tMatch between data series - OK"
            return True

    def GetConstrObsStatesHigh(self):
        """
        This method returns an array of boolean flags that indicate if an observed state variable is either
        constrained or not
        """
        constrHi = numpy.empty(self.GetNumVariables())
        i = 0
        for v in self.variables:
            constrHi[i] = v.GetConstraintHigh()
            i += 1
        return constrHi
    
    def GetConstrObsStatesLow(self):
        """
        This method returns an array of boolean flags that indicate if an observed state variable is either
        constrained or not
        """
        constrLow = numpy.empty(self.GetNumVariables())
        i = 0
        for v in self.variables:
            constrLow[i] = v.GetConstraintLow()
            i += 1
        return constrLow
    
    def GetConstrParsHigh(self):
        """
        This method returns an array of boolean flags that indicate if an estimated parameter is either
        constrained or not
        """
        constrHi = numpy.empty(self.GetNumParameters())
        i = 0
        for p in self.parameters:
            constrHi[i] = p.GetConstraintHigh()
            i += 1
        return constrHi
    
    def GetConstrParsLow(self):
        """
        This method returns an array of boolean flags that indicate if an estimated parameter is either
        constrained or not
        """
        constrLow = numpy.empty(self.GetNumParameters())
        i = 0
        for p in self.parameters:
            constrLow[i] = p.GetConstraintLow()
            i += 1
        return constrLow
    
    def GetCovMatrixStates(self):
        """
        This method returns the covariance matrix of the state variables
        """
        cov = numpy.diag(numpy.zeros(self.GetNumVariables()))
        i = 0
        for v in self.variables:
            cov[i,i] = v.GetCovariance()
            i += 1
        return cov
    
    def GetCovMatrixStatePars(self):
        """
        This method returns the covariance matrix of the state variables and parameters
        """
        cov = numpy.diag(numpy.zeros(self.GetNumVariables() + self.GetNumParameters()))
        i = 0
        for v in self.variables:
            cov[i,i] = v.GetCovariance()
            i += 1
        for p in self.parameters:
            cov[i,i] = p.GetCovariance()
            i += 1
        return cov
    
    def GetCovMatrixParameters(self):
        """
        This method returns the covariance matrix of the parameters
        """
        cov = numpy.diag(numpy.zeros(self.GetNumParameters()))
        i = 0
        for p in self.parameters:
            cov[i,i] = p.GetCovariance()
            i += 1
        return cov
    
    def GetCovMatrixOutputs(self):
        """
        This method returns the covariance matrix of the outputs
        """
        cov = numpy.diag(numpy.zeros(self.GetNumMeasuredOutputs()))
        i = 0
        for o in self.outputs:
            if o.IsMeasuredOutput():
                cov[i,i] = o.GetCovariance()
                i += 1
        return cov
          
    def GetFMU(self):
        """
        This method return the FMU associated to the model
        """
        return self.fmu
    
    def GetFmuFilePath(self):
        """
        This method returns the filepath of the FMU
        """
        return self.fmuFile
    
    def GetFmuName(self):
        """
        This method returns the name of the FMU associated to the model
        """
        return self.name
    
    def GetInputs(self):
        """
        Return the list of input variables associated to the FMU that have been selected
        """
        return self.inputs
    
    def GetInputByName(self, name):
        """
        This method returns the input contained in the list of inputs that has a name equal to 'name'
        """
        for var in self.inputs:
            if var.GetObject().name == name:
                return var
        return None
    
    def GetInputNames(self):
        """
        This method returns a list of names for each input
        """
        inputNames = []
        for inVar in self.inputs:
            # inVar is of type InOutVar and the object that it contains is a PyFMI variable
            inputNames.append(inVar.GetObject().name)
        return inputNames
    
    def GetInputReaders(self, t):
        """
        This method returns a list of functions that read the input for a given time
        """
        # TODO
        outputs = []
        for inVar in self.inputs:
            # inVar is of type InOutVar and the object that it contains is a PyFMI variable
            outputs.append(inVar.ReadFromDataSeries(t))
        return outputs
    
    def GetInputsTree(self):
        """
        This method returns the tree associated to the inputs of the model
        """
        return self.treeInputs
    
    def GetMeasuredOutputsValues(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsOut = numpy.zeros(self.GetNumMeasuredOutputs())
        i = 0
        for o in self.outputs:
            if o.IsMeasuredOutput():
                obsOut[i] = o.ReadValueInFMU(self.fmu)
                i += 1
        return obsOut
    
    def GetMeasuredDataOuputs(self, t):
        """
        This method returns the measured data value of the observed outputs at a given time
        instant t, that is a datetime object/string part of the datetimeIndex of the pandas.Series
        """
        # TODO: Done
        obsOut = numpy.zeros(shape=(1, self.GetNumMeasuredOutputs()))
        i = 0
        for o in self.outputs:
            if o.IsMeasuredOutput():
                obsOut[0,i] = o.ReadFromDataSeries(t)
                i += 1
        return  obsOut
    
    def GetMeasuredOutputDataSeries(self):
        """
        This method returns the data series associated to each measured output
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        outDataSeries = []
        for o in self.outputs:
            if o.IsMeasuredOutput():
                outDataSeries.append(o)
        
        # Try to align the measured output data
        self.CheckDataList(outDataSeries, align = True)
        
        # Now transform it into a matrix with time as first column and the measured outputs
        time = outDataSeries[0].GetDataSeries().index
        
        # Create the empty matrix
        Npoints = len(time)
        Nouts = self.GetNumMeasuredOutputs()
        dataMatrix = numpy.zeros(shape=(Npoints, Nouts+1))
        
        # Define the first column as the time
        dataMatrix[:,0] = time
        
        # Put the other values in the following columns
        i = 1
        for o in outDataSeries:
            dataMatrix[:,i] = o.GetDataSeries().values
            i += 1
        
        return dataMatrix 
    
    def GetNumInputs(self):
        """
        This method returns the total number of input variables of the FMU model
        """
        return len(self.inputs)
    
    def GetNumOutputs(self):
        """
        This method returns the total number of output variables of the FMU model
        """
        return len(self.outputs)
    
    def GetNumMeasuredOutputs(self):
        """
        This method returns the number of measured output variables of the FMU model
        """
        i = 0
        for o in self.outputs:
            if o.IsMeasuredOutput():
                i += 1
        return i
    
    def GetNumParameters(self):
        """
        This method returns the number of parameters of the FMU model to be estimated or identified
        """
        return len(self.parameters)
    
    def GetNumVariables(self):
        """
        This method returns the number of variables of the FMU model to be estimated or identified
        """
        return len(self.variables)
    
    def GetNumStates(self):
        """
        This method returns the total number of states variables of the FMU model
        """
        return self.N_STATES
    
    def GetOutputs(self):
        """
        Return the list of output variables associated to the FMU that have been selected
        """
        return self.outputs
    
    def GetOutputByName(self, name):
        """
        This method returns the output contained in the list of outputs that has a name equal to 'name'
        """
        for var in self.outputs:
            if var.GetObject().name == name:
                return var
        return None
    
    def GetOutputNames(self):
        """
        This method returns a list of names for each output
        """
        outputNames = []
        for outVar in self.outputs:
            # outVar is of type InOutVar and the object that it contains is a PyFMI variable
            outputNames.append(outVar.GetObject().name)
        return outputNames
    
    def GetOutputsValues(self):
        """
        This method return a vector that contains the values of the outputs of the model
        """
        obsOut = numpy.zeros(self.GetNumOutputs())
        i = 0
        for o in self.outputs:
            obsOut[i] = o.ReadValueInFMU(self.fmu)
            i += 1
        return obsOut
    
    def GetOutputsTree(self):
        """
        This method returns the tree associated to the outputs of the model
        """
        return self.treeOutputs
    
    def GetParameters(self):
        """
        Return the list of parameters contained by the FMU that have been selected
        """
        return self.parameters
    
    def GetParametersMin(self):
        """
        This method return a vector that contains the values of the min value possible for the estimated parameters
        """
        minValues = numpy.zeros(self.GetNumParameters())
        i = 0
        for p in self.parameters:
            minValues[i] = p.GetMinValue()
            i += 1
        return minValues
    
    def GetParametersMax(self):
        """
        This method return a vector that contains the values of the max value possible for the estimated parameters
        """
        maxValues = numpy.zeros(self.GetNumParameters())
        i = 0
        for p in self.parameters:
            maxValues[i] = p.GetMaxValue()
            i += 1
        return maxValues
    
    def GetParameterNames(self):
        """
        This method returns a list of names for each state variables observed
        """
        parNames = []
        for par in self.variables:
            # EstimationVariable
            parNames.append(par.name)
        return parNames
    
    def GetParametersValues(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsPars = numpy.zeros(self.GetNumParameters())
        i = 0
        for p in self.parameters:
            obsPars[i] = p.ReadValueInFMU(self.fmu)
            i += 1
        return obsPars
    
    def GetParametersTree(self):
        """
        This method returns the tree associated to the parameters of the model
        """
        return self.treeParameters
    
    def GetProperties(self):
        """
        This method returns a tuple containing the properties of the FMU
        """
        return (self.name, self.author, self.description, self.type, self.version, self.guid, self.tool, self.numStates)
    
    def GetReal(self, var):
        """
        Get a real variable in the FMU model, given the PyFmi variable description
        """
        return self.fmu.get_real(var.value_reference)[0]
    
    def GetSimulationOptions(self):
        """
        This method returns the simulation options of the simulator
        """
        return self.opts
    
    def GetState(self):
        """
        This method return a vector that contains the values of the entire state variables of the model
        """
        return self.fmu._get_continuous_states()
    
    def GetStateObservedValues(self):
        """
        This method return a vector that contains the values of the observed state variables of the model
        That are listed in self.variables
        """
        obsState = numpy.zeros(self.GetNumVariables())
        i = 0
        for v in self.variables:
            obsState[i] = v.ReadValueInFMU(self.fmu)
            i += 1
        return obsState
    
    def GetStateObservedMin(self):
        """
        This method return a vector that contains the values of the min value possible for the observed states
        """
        minValues = numpy.zeros(self.GetNumVariables())
        i = 0
        for v in self.variables:
            minValues[i] = v.GetMinValue()
            i += 1
        return minValues
    
    def GetStateObservedMax(self):
        """
        This method return a vector that contains the values of the max value possible for the observed states
        """
        maxValues = numpy.zeros(self.GetNumVariables())
        i = 0
        for v in self.variables:
            maxValues[i] = v.GetMaxValue()
            i += 1
        return maxValues
    
    def GetTree(self, objectTree, variability, causality, onlyStates = False, pedantic = False):
        """
        This function, provided one tree, populates it.
        The tree is used to represent the parameters, variables, input, outputs with the dot notation,
        and used as support for the graphical object tree
        """
        try:
            
            # Take the variable of the FMU that have the specified variability and causality
            # the result is a dictionary which has as key the name of the variable with the dot notation
            # and as element a class of type << pyfmi.fmi.ScalarVariable >>
            # Alias variable removed for clarity.
            dictParameter = self.fmu.get_model_variables(include_alias = False, variability = variability, causality = causality)
            
            if onlyStates and pedantic:
                print "Ref. values of the states: "+str(self.StateValueReferences)
            
            for k in dictParameter.keys():
                ####################################################################################
                # TODO: check if it's true to don't add now the variables which have derivatives
                #       I think in general is not true, but be careful with the extraction of the 
                #       name with the dot notation
                ####################################################################################
                if "der(" not in k:
                    
                    # Split the variable name that is written with the dot notation
                    strNames = k.split(".")
                    
                    # Given the vector of names obtained with the dot notation creates the branches of the tree
                    # and name correctly each node and leaf.
                    #
                    # The object attached to each leaf of the tree is << dictParameter[k] >>
                    # which is of type << pyfmi.fmi.ScalarVariable >>
                    if onlyStates:
                        
                        # Add the variables that are in the state vector of the system
                        if dictParameter[k].value_reference in self.StateValueReferences:
                            objectTree.addFromString(strNames, dictParameter[k])
                            if pedantic:
                                print str(k) + " with Ref. value =" + str(dictParameter[k].value_reference)
                                print str(k) + " with Name =" + str(dictParameter[k].name)
                                print dictParameter[k]
                            
                    else:
                        objectTree.addFromString(strNames, dictParameter[k])
            
            if pedantic:
                print objectTree.getAll()
            
            return True
        
        except IndexError:
            # An error can occur if the FMU has not yet been loaded
            print "FMU not yet loaded..."
            return False
    
    def GetTreeByType(self, Type):
        """
        This method given a string that describes a given type of tree, it returns that tree
        """
        if Type == Strings.PARAMETER_STRING:
            return self.treeParameters
        if Type == Strings.VARIABLE_STRING:
            return self.treeVariables
        if Type == Strings.INPUT_STRING:
            return self.treeInputs
        if Type == Strings.OUTPUT_STRING:
            return self.treeOutputs
        else:
            print "No Match between the type passes and the available trees"
            return None
    
    def GetVariables(self):
        """
        Return the list of state variables contained by the FMU that have been selected
        """
        return self.variables
    
    def GetVariableInfo_Numeric(self, variableInfo):
        """
        Given a variableInfo object that may be related either to a parameter, a state variable, an input or a output
        This function returns the values and details associated to it.
        """
        
        try:
            # Take the data type associated to the variable
            Type  = self.fmu.get_variable_data_type(variableInfo.name)
            
            # According to the data type read, select one of these methods to get the information
            if Type == pyfmi.fmi.FMI_REAL:
                value = self.fmu.get_real( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_INTEGER:
                value = self.fmu.get_integer( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_BOOLEAN:
                value = self.fmu.get_boolean( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_ENUMERATION:
                value = self.fmu.get_int( variableInfo.value_reference )
            elif Type == pyfmi.fmi.FMI_STRING:
                value = self.fmu.get_string( variableInfo.value_reference )
            else:
                print "OnSelChanged::FMU-EXCEPTION :: The type is not known"
                value = 0.0
 
            # TODO: check the min and max value if the variables are not real or integers
            Min   = self.fmu.get_variable_min(variableInfo.name)
            Max   = self.fmu.get_variable_max(variableInfo.name)
                
            try:
                start = self.fmu.get_variable_start(variableInfo.name)
            except pyfmi.fmi.FMUException:
                print "Default start value defined as 0.0"
                start = 0.0
            
            return (type, value, start, Min, Max)
        
        except pyfmi.fmi.FMUException:
                # if the real value is not present for this parameter/variable
                print "OnSelChanged::FMU-EXCEPTION :: No real value to read for this variable"
                return (None, None, None, None, None)
    
    def GetVariableInfo(self, variableInfo):
        """
        Given a variableInfo object that may be related either to a parameter, a state variable, an input or a output
        This function returns the values and details associated to it.
        """
        
        try:
            # Take the data type associated to the variable
            Type  = self.fmu.get_variable_data_type(variableInfo.name)
            
            # According to the data type read, select one of these methods to get the information
            if Type == pyfmi.fmi.FMI_REAL:
                value = self.fmu.get_real( variableInfo.value_reference )
                strType = "Real"
            elif Type == pyfmi.fmi.FMI_INTEGER:
                value = self.fmu.get_integer( variableInfo.value_reference )
                strType = "Integer"
            elif Type == pyfmi.fmi.FMI_BOOLEAN:
                value = self.fmu.get_boolean( variableInfo.value_reference )
                strType = "Boolean"
            elif Type == pyfmi.fmi.FMI_ENUMERATION:
                value = self.fmu.get_int( variableInfo.value_reference )
                strType = "Enum"
            elif Type == pyfmi.fmi.FMI_STRING:
                value = self.fmu.get_string( variableInfo.value_reference )
                strType = "String"
            else:
                print "OnSelChanged::FMU-EXCEPTION :: The type is not known"
                value = [""]
                strType = "Unknown"
 
            # TODO: check the min and max value if the variables are not real or integers
            Min   = self.fmu.get_variable_min(variableInfo.name)
            Max   = self.fmu.get_variable_max(variableInfo.name)
                
            try:
                start = str(self.fmu.get_variable_start(variableInfo.name))
                fixed = self.fmu.get_variable_fixed(variableInfo.name)
                start = start+" (fixed ="+str(fixed)+")"
            except pyfmi.fmi.FMUException:
                start = ""
                
            strVal = str(value[0])
            strMin = str(Min)
            strMax = str(Max)
            if min < -1.0e+20:
                strMin = "-Inf"
            if max > 1.0e+20:
                strMax = "+Inf"
            
            return (strType, strVal, start, strMin, strMax)
        
        except pyfmi.fmi.FMUException:
                # if the real value is not present for this parameter/variable
                print "OnSelChanged::FMU-EXCEPTION :: No real value to read for this variable"
                return ("", "", "", "", "")
    
    def GetVariableNames(self):
        """
        This method returns a list of names for each state variables observed
        """
        varNames = []
        for var in self.variables:
            # EstimationVariable
            varNames.append(var.name)
        return varNames
    
    def GetVariableObject(self, name = None):
        """
        This method returns a PyFMI variable given its name
        """
        if name != None and name != "":
            if self.fmu != None:
                try:
                    return self.fmu.get_model_variables()[name]
                except Exception:
                    print "The variable or parameter: "+str(name)+" is not available in the list:"
                    print self.fmu.get_model_variables().keys()
                    return None
            else:
                print "The FMU model has not yet been set. Impossible return the variable "+str(name)
                return None
        else:
            print "Impossible to look for the name because it is None or empty"
            return None
    
    def GetVariablesTree(self):
        """
        This method returns the tree associated to the state variables of the model
        """
        return self.treeVariables
    
    def InitializeSimulator(self, startTime = None):
        """
        This method performs a very short simulation to initialize the model.
        The next times the model will be simulated without the initialization phase.
        By default the simulation is performed at the initial time of the input data series, but the
        user can specify an other point.
        """
        # TODO: Done
        # Load the inputs and check if any problem. If any exits.
        # Align inputs while loading.
        if not self.LoadInput(align = True):
            return False
        
        # Load the outputs and check if any problems. If any exits.
        if not self.LoadOutputs():
            return False
        
        # Take the time series: the first because now they are all the same (thanks to alignment)
        time = self.inputs[0].GetDataSeries().index
        
        # Define the initial time for the initialization
        if startTime == None:
            # Start time not specified, start from the beginning
            index = 0
        else:
            
            # Check that the type of start time is of type datetime
            if not isinstance(startTime, datetime.datetime):
                raise TypeError("The parameter startTime has to be of datetime.datetime type")
                
            # Start time specified, start from the closest point
            if startTime >= time[0] and startTime <= time[-1]:
                index = 0
                for t in time:
                    if t < startTime:
                        index += 1
                    else:
                        break
            else:
                index = 0
                raise IndexError("The value selected as initialization start time is outside the time frame")
                
        # Once the index is know it can be used to define the start_time
        start_time = time[index]
        
        # Take all the data series
        Ninputs = len(self.inputs)
        start_input = numpy.zeros((1, Ninputs))
        start_input_1 = numpy.zeros((1, Ninputs))
        start_input_2 = numpy.zeros((1, Ninputs))
        i = 0
        if index == 0:
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.GetDataSeries().values).reshape(-1,1)
                start_input[0, i] = dataInput[index,0]
                i += 1
        else:
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.GetDataSeries().values).reshape(-1,1)
                start_input_1[0, i] = dataInput[index-1,0]
                start_input_2[0, i] = dataInput[index,0]
                
                # Linear interpolation between the two values
                dt0 = (time[index] - start_time).total_seconds()
                dT1 = (start_time  - time[index-1]).total_seconds()
                DT  = (time[index] - time[index-1]).total_seconds()
                
                # Perform the interpolation
                start_input[0, i] = (dt0*start_input_1[0, i] + dT1*start_input_2[0, i])/DT
                
                i += 1
               
        # Initialize the model for the simulation
        self.opts["initialize"] = True
        
        try:
            # Simulate from the initial time to initial time + epsilon
            # thus we have 2 points
            
            # Create the input objects for the simulation that initializes
            Input = numpy.hstack((start_input, start_input))
            Input = Input.reshape(2,-1)
            
            time = pd.DatetimeIndex([start_time, start_time])
            
            # Run the simulation, remember that
            # time has to be a dateteTimeIndex and Input has to be a numpy.matrix
            self.Simulate(time = time, Input = Input)
            self.opts["initialize"] = False
            
            # Initialize the selected variables and parameters to the values indicated 
            # Done after very small simulation because there can be some internal parameters that defines
            # the initial value and may override the initialization with the indicated values
            for v in self.variables:
                v.ModifyInitialValueInFMU(self.fmu)
            for p in self.parameters:
                p.ModifyInitialValueInFMU(self.fmu)
            
            return True
        
        except ValueError:
            print "First simulation for initialize the model failed"
            return False
    
    def IsParameterPresent(self, obj):
        """
        This method returns true is the parameter is contained in the list of parameters of the model
        """
        val_ref = obj.value_reference
        for p in self.parameters:
            if p.value_reference == val_ref:
                # there is already a parameter in the list with the same value_reference
                print "There is already a parameter in the list with the same value reference: "+str(val_ref)
                return True
        return False
    
    def IsVariablePresent(self, obj):
        """
        This method returns true is the variable is contained in the list of variable of the model
        """
        val_ref = obj.value_reference
        for v in self.variables:
            if v.value_reference == val_ref:
                # there is already a variable in the list with the same value_reference
                print "There is already a variable in the list with the same value reference: "+str(val_ref)
                return True
        return False
    
    def LoadInput(self, align = True):
        """
        This method loads all the input data series. It returns a boolean if the import was successful.
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        LoadedInputs = True
        for inp in self.inputs:
            LoadedInputs = LoadedInputs and inp.ReadDataSeries()
        
        if not LoadedInputs:
            print "An error occurred while loading the inputs"
        else:
            # A check on the input data series should be performed: Are the initial times, final times and number of point
            # aligned? If not perform an interpolation to align them is done. The boolean flag align deals with this.
            print "Check the input data series..."
            if not self.CheckInputData(align):
                print "Re-Check the input data series..."
                return self.CheckInputData(align)
            
        return LoadedInputs
    
    def LoadOutputs(self):
        """
        This method loads all the output data series. It returns a boolean if the import was successful
        """
        # TODO: Done
        # Get all the data series from the CSV files (for every input of the model)
        LoadedOutputs = True
        for o in self.outputs:
            if o.IsMeasuredOutput():
                LoadedOutputs = LoadedOutputs and o.ReadDataSeries()
        
        if not LoadedOutputs:
            print "An error occurred while loading the outputs"
        
        return LoadedOutputs
    
    def ReInit(self, fmuFile, result_handler = None, solver = None, atol = 1e-6, rtol = 1e-4, setTrees = False, verbose=None):
        """
        This function reinitializes the FMU associated to the model
        """
        print "Previous FMU was: ",self.fmu
        print "Reinitialized model with: ",fmuFile
        if self.fmu != None:
            self.fmu = None
        self.__init__(fmuFile, result_handler, solver, atol, rtol, setTrees, verbose)
    
    def RemoveParameter(self, obj):
        """
        This method removes one object to the list of parameters. This list contains only the parameters that 
        will be modified during the further analysis
        """
        try:
            index = self.parameters.index(obj)
            self.parameters.pop(index)
            return True
        except ValueError:
            # the object cannot be removed because it is not present
            return False
        
    def RemoveParameters(self):
        """
        This method removes all the objects from the list of parameters.
        """
        self.parameters = []
    
    def RemoveVariable(self, obj):
        """
        This method remove one object to the list of variables. This list contains only the parameters that 
        will be modified during the further analysis
        """
        try:
            index = self.variables.index(obj)
            self.variables.pop(index)
            return True
        except ValueError:
            # the object cannot be removed because it is not present
            return False
    
    def RemoveVariables(self):
        """
        This method removes all the objects from the list of parameters.
        """
        self.variables = []
    
    def unloadFMU(self):
        """
        This method unload the FMU model and it deallocate the resources associated to it.
        This is necessary is an other FMU model needs to be loaded.
        """
        del(self.fmu)
    
    def __SetFMU(self, fmuFile, result_handler, solver, atol, rtol, verbose):
        """
        This method associate an FMU to a model, if not yet assigned
        """
        if self.fmu == None:
            
            #TODO:
            # See what can be done in catching the exception/propagating it
            self.fmu = pyfmi.load_fmu(fmuFile)
                
            # Get the options for the simulation
            self.opts = self.fmu.simulate_options()
            
            # Define the simulation options
            self.SetSimulationOptions(result_handler, solver, atol, rtol, verbose)
            
            # Define the standard value for the result file
            self.SetResultFile(None)
            
            # set the number of states
            self.N_STATES = len(self.GetState())
            
            # get the value references of the state variables
            self.StateValueReferences = self.fmu.get_state_value_references()
            
            # Properties of the FMU
            self.name = str(self.fmu.get_name())
            self.author = str(self.fmu.get_author())
            self.description = str(self.fmu.get_description())
            self.type = str(self.fmu.__class__.__name__)
            self.version = str(self.fmu.version)
            self.guid = str(self.fmu.get_guid())
            self.tool = str(self.fmu.get_generation_tool())
            [Ncont, Nevt] = self.fmu.get_ode_sizes()
            self.numStates = "( "+str(Ncont)+" , "+str(Nevt)+" )"
            
            # prepare the list of inputs and outputs
            self.__SetInputs()
            self.__SetOutputs()
            
        else:
            print "WARNING: The fmu has already been assigned to this model! Check your code!"
        
    def __SetInputsTree(self):
        """
        This method updates the inputs tree structure
        """
        if not self.__SetGeneralizedTree(None, 0):
            print "Problems while creating the inputs tree"
            self.treeInputs = Tree(Strings.INPUT_STRING)
            
    def __SetGeneralizedTree(self, variability, causality, onlyStates = False, pedantic = False):
        """
        This method populates 
        """
        if variability == 1 and causality == None:
            # parameters
            done = self.GetTree(self.treeParameters, variability, causality, onlyStates, pedantic)
        if variability == 3 and causality == None:
            # state variables
            done = self.GetTree(self.treeVariables, variability, causality, onlyStates, pedantic)
        if variability == None and causality == 1:
            # outputs
            done = self.GetTree(self.treeOutputs, variability, causality, onlyStates, pedantic)
        if variability == None and causality == 0:
            # inputs
            done = self.GetTree(self.treeInputs, variability, causality, onlyStates, pedantic)
            
        return done
    
    def __SetInputs(self):
        """
        This function sets the input variables of a model
        """
        self.__SetInOutVar(None, 0)
    
    def __SetInOutVar(self, variability, causality):
        """
        "Input"
            causality = 0
            variability = None
        "Outputs"
            causality = 1
            variability = None
        """
        # Take the variable of the FMU that have the specified variability and causality
        # the result is a dictionary which has as key the name of the variable with the dot notation
        # and as element a class of type << pyfmi.fmi.ScalarVariable >>
        # Alias variable removed for clarity.
        dictVariables = self.fmu.get_model_variables(include_alias = False, variability = variability, causality = causality)
            
        for k in dictVariables.keys():
            # The object attached to each leaf of the tree is << dictParameter[k] >>
            # which is of type << pyfmi.fmi.ScalarVariable >>
            
            var = InOutVar()
            var.SetObject(dictVariables[k])
            
            if variability == None and causality ==0:
                # input
                self.inputs.append(var)
            if variability == None and causality ==1:
                # output
                self.outputs.append(var)

    def __SetOutputs(self):
        """
        This function sets the output variables of a model
        """
        self.__SetInOutVar(None, 1)
    
    def __SetOutputsTree(self):
        """
        This method updates the outputs tree structure
        """
        if not self.__SetGeneralizedTree(None, 1):
            print "Problems while creating the outputs tree"
            self.treeOutputs = Tree(Strings.OUTPUT_STRING)
    
    def __SetParametersTree(self):
        """
        This method updates the parameters tree structure
        """
        if not self.__SetGeneralizedTree(1, None):
            print "Problems while creating the parameters tree"
            self.treeParameters = Tree(Strings.PARAMETER_STRING)
    
    def SetResultFile(self, fileName):
        """
        This method modifies the name of the file that stores the simulation results
        """
        if fileName!= None:
            self.opts["result_file_name"] = fileName
        else:
            self.opts["result_file_name"] = ""
    
    def SetSimulationOptions(self, result_handler, solver, atol, rtol, verbose):
        """
        This method set the options of the simulator
        """
        # The result handling can be one of
        # "file", "memory", "custom" (in the latter case a result handler has to be specified)
        # By default they are on memory
        if result_handler != None and result_handler in Strings.SIMULATION_OPTION_RESHANDLING_LIST:
            self.opts[Strings.SIMULATION_OPTION_RESHANDLING_STRING] = result_handler
        else:
            self.opts[Strings.SIMULATION_OPTION_RESHANDLING_STRING] = Strings.RESULTS_ON_MEMORY_STRING
        
        
        # Set solver verbose level
        if verbose != None and  verbose in Strings.SOLVER_VERBOSITY_LEVELS:
            for s in Strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][Strings.SOLVER_OPTION_VERBOSITY_STRING] = verbose
        else:
            for s in Strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][Strings.SOLVER_OPTION_VERBOSITY_STRING] = Strings.SOLVER_VERBOSITY_QUIET
        
              
        # Set the absolute and relative tolerance of each solver, otherwise the default value
        # is left
        if atol != None and atol > 0 and numpy.isreal(atol):
            for s in Strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][Strings.SOLVER_OPTION_ATOL_STRING] = atol
        if rtol != None and rtol > 0 and numpy.isreal(rtol):
            for s in Strings.SOLVER_NAMES_OPTIONS:   
                self.opts[s][Strings.SOLVER_OPTION_RTOL_STRING] = rtol
        
    def SetState(self, stateVector):
        """
        This method sets the entire state variables vector of the model
        """
        self.fmu._set_continuous_states(stateVector)
    
    def SetReal(self, var, value):
        """
        Set a real variable in the FMU model, given the PyFmi variable description
        """
        self.fmu.set_real(var.value_reference, value)
        return
    
    def SetStateSelected(self, vector):
        """
        This method sets the state variable contained in the list self.variables
        to the values passed by the vector
        """
        if len(vector) == len(self.variables):
            # The vector have compatible dimensions
            i = 0
            for v in self.variables:
                self.fmu.set_real(v.value_reference, vector[i])
                i += 1
            return True
        else:
            # the vectors are not compatibles
            return False
    
    def SetParametersSelected(self, vector):
        """
        This method sets the parameters contained in the list self.parameters
        to the values passed by the vector
        """
        if len(vector) == len(self.parameters):
            # The vector have compatible dimensions
            i = 0
            for p in self.parameters:
                self.fmu.set_real(p.value_reference, vector[i])
                i += 1
            return True
        else:
            # the vectors are not compatibles
            return False
    
    def __SetTrees(self):
        """
        This method sets the trees associated to all parameters, variables, inbputs and outputs
        """
        self.__SetInputsTree()
        self.__SetOutputsTree()
        self.__SetParametersTree()
        self.__SetVariablesTree()
        pass
    
    def __SetVariablesTree(self):
        """
        This method updates the variables tree structure
        """
        if not self.__SetGeneralizedTree(3, None, True):
            print "Problems while creating the variables tree"
            self.treeVariables = Tree(Strings.VARIABLE_STRING)
    
    def Simulate(self, start_time = None, final_time = None, time = pd.DatetimeIndex([]), Input = None, complete_res = False):
        """
        This method simulates the model from the start_time to the final_time, using a given set of simulation
        options. Since it may happen that a simulation fails without apparent reason (!!), it is better to 
        simulate again the model if an error occurs. After N_TRIES it stops.
        input = [[u1(T0), u2(T0), ...,uM(T0)],
                 [u1(T1), u2(T1), ...,uM(T1)],
                 ...
                 [u1(Tend), u2(Tend), ...,uM(Tend)]]
        """
        # TODO
        
        # Number of input variables needed by the model
        Ninputs = len(self.inputs)
        
        # Check if the parameter time has been provided
        if len(time) == 0:
            # Take the time series: the first because now they are all the same
            for inp in self.inputs:
                time = inp.GetDataSeries().index
                break
        else:
            # Check that the type of the time vector is of type pd.DatetimeIndex
            if not isinstance(time, pd.DatetimeIndex):
                raise TypeError("The parameter time has to be a vector of type pd.DatetimeIndex")
            
        # Define initial start time in seconds
        if start_time == None:
            start_time = time[0]
        else:
            # Check that the type of start time is of type datetime
            if not isinstance(start_time, datetime.datetime):
                raise TypeError("The parameter start_time is of type %s, it has to be of datetime.datetime type." % (str(start_time)))
            # Check if the start time is within the range
            if not (start_time >= time[0] and start_time <= time[-1]):
                raise IndexError("The value selected as initialization start time is outside the time frame")
            
        start_time_sec = (start_time - time[0]).total_seconds()
        
        # Define the final time in seconds
        if final_time == None:
            final_time = time[-1]
        else:
            # Check that the type of start time is of type datetime
            if not isinstance(final_time, datetime.datetime):
                raise TypeError("The parameter final_time is of type %s, it has to be of datetime.datetime type." % (str(start_time)))
            # Check if the final time is within the range
            if not (final_time >= time[0] and final_time <= time[-1]):
                raise IndexError("The value selected as initialization start time is outside the time frame")
            # Check that the final time is after the start time
            if not (final_time >= start_time):
                raise IndexError("The final_time %s has to be after the start time %s." % \
                                 (str(final_time), str(start_time)))
        final_time_sec = (final_time - time[0]).total_seconds()
            
        # Transforms to seconds with respect to the first element
        Npoints = len(time)
        time_sec = numpy.zeros((Npoints,1))
        for i in range(Npoints):
            time_sec[i,0] = (time[i] - time[0]).total_seconds()
        
        # Convert to numpy matrix in case it will be stacked in a matrix
        time_sec = numpy.matrix(time_sec)
        
        # Reshape to be consistent
        time_sec  = time_sec.reshape(-1, 1)
        
        if Input == None:
            # Take all the data series
            inputMatrix = numpy.matrix(numpy.zeros((Npoints, Ninputs)))
            
            i = 0
            for inp in self.inputs:
                dataInput = numpy.matrix(inp.GetDataSeries().values).reshape(-1,1)
                inputMatrix[:, i] = dataInput[:,:]
                i += 1
            # Define the input trajectory
            V = numpy.hstack((time_sec, inputMatrix))
            
        else:
            # Reshape to be consistent
            Input = Input.reshape(-1, Ninputs)
            # Define the input trajectory
            V = numpy.hstack((time_sec, Input))
        
        # The input trajectory must be an array, otherwise pyfmi does not work
        u_traj  = numpy.array(V)
        
        # Create input object
        names = self.GetInputNames()
        input_object = (names, u_traj)
        
        # TODO
        # Associate functions rather than a matrix that contains all the values
        # input_object = (names, self.GetInputReaders)
        
        # Start the simulation
        simulated = False
        i = 0
        while not simulated and i < self.SIMULATION_TRIES:
            try:
                res = self.fmu.simulate(start_time = start_time_sec, input = input_object, final_time = final_time_sec, options = self.opts)
                simulated = True
            except ValueError:
                print "Simulation of the model failed, try again"
                i += 1 
        
        # Check if the simulation has been done, if not through an exception
        if not simulated:
            raise Exception
        
        # Obtain the results
        # TIME in seconds has to be converted to datetime
        # and it has to maintain the same offset specified by the input time series in t[0]
        offset = time[0] - pd.to_datetime(res[Strings.TIME_STRING][0])
        t     = pd.to_datetime(res[Strings.TIME_STRING], unit="s") + offset
        
        # Get the results, either all or just the selected ones
        if complete_res == False:
            # OUTPUTS
            output_names = self.GetOutputNames()
            results = {}
            for name in output_names:
                results[name] = res[name]
            # STATES OBSERVED
            var_names = self.GetVariableNames()
            for name in var_names:
                results[name] = res[name]
            # PARAMETERS
            par_names = self.GetParameterNames()
            for name in par_names:
                results[name] = res[name]
            
            # THE OVERALL STATE
            results["__ALL_STATE__"]=self.GetState()
            results["__OBS_STATE__"]=self.GetStateObservedValues()
            results["__PARAMS__"]=self.GetParametersValues()
            results["__OUTPUTS__"]=self.GetMeasuredOutputsValues()
            results["__ALL_OUTPUTS__"]=self.GetOutputsValues()
            
        else:
            # All the results are given back
            results = res
            
        # Return the results
        return (t, results)
    
    def __str__(self):
        """
        Built-in function to print description of the object
        """
        string = "\nFMU based Model:"
        string += "\n-File: "+str(self.fmuFile)
        string += "\n-Name: "+self.name
        string += "\n-Author: "+self.author
        string += "\n-Description: "+ self.description
        string += "\n-Type: "+self.type
        string += "\n-Version: "+self.version
        string += "\n-GUID: "+self.guid
        string += "\n-Tool: "+self.tool
        string += "\n-NumStates: "+self.numStates+"\n"
        return string
    
    def ToggleParameter(self, obj):
        """
        If the parameter is already present it is removed, otherwise it is added
        """
        if self.IsParameterPresent(obj):
            self.RemoveParameter(obj)
        else:
            self.AddParameter(obj)
    
    def ToggleVariable(self, obj):
        """
        If the variable is already present it is removed, otherwise it is added
        """
        if self.IsVariablePresent(obj):
            self.RemoveVariable(obj)
        else:
            self.AddVariable(obj)