'''
Created on Oct 6, 2014

@author: Steven B. Nelson, Enterprise Infrastructure Architect
        NetApp, Inc.
        
WfaRest - demonstration .py showing how to use the Wfa class.
*** REQUIRES Python 2.7.x and above ***
*** IS NOT TESTED WITH Python 3.x ***
'''

if __name__ == '__main__':
    pass

# Import the class (obviously)
from Wfa import Wfa
from time import sleep

# Instantiate an instance with the host, workflow name, username, and password
wfa = Wfa("cyberman", "Create an NFS Volume", "admin", "sp1Tfir3")
cycleTime = 5

# Map wfa parameters to internal variables...
wfaParamMap = {
               'VolumeName' : 'volName',
               'VolumeSize' : 'volSize',
               'ReadWriteHosts' : 'rwHosts',
               'ReadOnlyHosts' : 'roHosts',
               'RootHosts' : 'rootHosts'
               }

# these are the internal variables.  We could have just as easily set them manually 
# in the paramMap, but I wanted to keep it clean for demonstration purposes.
# volume size is in GB * 1.25 according to the workflow
wfaParams = {
             'volName' : "test11",
             'volSize' : 1,
             'rwHosts' : "enterprise, intrepid",
             'roHosts' : None,
             'rootHosts' : None
             }

newWfaParamMap = {}
for paramKey in wfaParamMap:
    newWfaParamMap[paramKey] = wfaParams[wfaParamMap[paramKey]]

# How to get the workflow parameters that are possible...
# We get the raw XML here...
wfaXml = wfa.getRestResponse(wfa.workflowQueryURI)

# Then use it to get both sets of information.
wfa.printWorkflowInputList(wfaXml)
wfa.printWorkflowOutputList(wfaXml)

# How to execute a workflow.
wfa.setupWorkflow(newWfaParamMap)
wfa.executeWorkflow()

# Get the initial status (simple status)
wfaStatus = wfa.getSimpleJobStatus()

# This simply shows how you can query the job status until completion (and even after...)
# We use the job dictionary to get the job ID from WFA of this instance.
while(wfaStatus == "OK"):
    wfaStatus = wfa.getSimpleJobStatus()
    print "Current status for job " + wfa.jobDict['jobId'] + ": " + wfaStatus
    sleep(cycleTime)

# An example of handling success/failure.
if(wfaStatus == 'FAILED'):
    print "Job: " + wfa.jobDict['jobId'] + " failed at command " + wfa.jobDict['wfCmdExecuting'] + " of " + wfa.jobDict['wfCmdTotal']
    print "\tError message: " + wfa.jobDict['jobError']
elif(wfaStatus == 'DONE'):
    print "Job: " + wfa.jobDict['jobId'] + " completed successfully."
    for retParam in wfa.jobDict['returnParams']:
        print retParam + " "  + wfa.jobDict['returnParams'][retParam]