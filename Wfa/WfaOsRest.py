'''
Created on Oct 12, 2014

@author: Steven
'''

if __name__ == '__main__':
    pass

from Wfa import WfaOs
from time import sleep

cycletime = 5

myWfaDict = {
             'wfaServer' : 'cyberman',
             'wfaUser' : 'admin',
             'wfaPw' : 'sp1Tfir3',
             'wfaOperation' : 'create_share',
             'wfaPlatform' : 'cdot',
             'osProject' : 'manila',
             'wfaExtraSpec' : {
                               'clusName' : 'sbn-clus2',
                               'vserverName' : 'vserver821'
                               }
             }

shareName = 'random UUID'
shareSize = 10
shareProto = 'nfs'
wfa = WfaOs(myWfaDict)

for param in wfa.wfaDict['wfaParamMap']:
    wfa.wfaDict['wfaParamMap'][param] = eval(wfa.wfaDict['wfaParamMap'][param]) 

wfa.appendExtraSpec()

# How to get the workflow parameters that are possible...
# We get the raw XML here...
wfaXml = wfa.getRestResponse(wfa.workflowQueryURI)

# Then use it to get both sets of information.
wfa.printWorkflowInputList(wfaXml)
wfa.printWorkflowOutputList(wfaXml)


