# ChaosMesh KPI Collection Evidence

started_at: 2026-06-05T16:45:31.182079
finished_at: 2026-06-05T16:49:25.294307
samples: 120
interval_seconds: 1.0
fault_window_samples: 45-74
chaos_yaml: scripts/chaos-online-boutique-productcatalog-podkill.yaml
output_csv: D:\HuaweiMoveData\Users\13976\Documents\New project\_teammate_project_analysis\final_project\data\online_boutique_chaosmesh_metrics.csv

## Events

```text
sample 45: applied scripts\chaos-online-boutique-productcatalog-podkill.yaml
```
```text
Name:         online-boutique-productcatalog-pod-kill
Namespace:    online-boutique
Labels:       <none>
Annotations:  <none>
API Version:  chaos-mesh.org/v1alpha1
Kind:         PodChaos
Metadata:
  Creation Timestamp:  2026-06-05T08:46:54Z
  Finalizers:
    chaos-mesh/records
  Generation:        5
  Resource Version:  109107
  UID:               24bf0d21-87fa-48f1-8e6c-fb30a44d0cbd
Spec:
  Action:  pod-kill
  Mode:    one
  Selector:
    Label Selectors:
      App:  productcatalogservice
    Namespaces:
      online-boutique
Status:
  Conditions:
    Status:  False
    Type:    Paused
    Status:  True
    Type:    Selected
    Status:  True
    Type:    AllInjected
    Status:  False
    Type:    AllRecovered
  Experiment:
    Container Records:
      Events:
        Operation:      Apply
        Timestamp:      2026-06-05T08:46:54Z
        Type:           Succeeded
      Id:               online-boutique/productcatalogservice-c4cfd98fb-zm88k
      Injected Count:   1
      Phase:            Injected
      Recovered Count:  0
      Selector Key:     .
    Desired Phase:      Run
Events:
  Type    Reason           Age   From            Message
  ----    ------           ----  ----            -------
  Normal  FinalizerInited  2s    initFinalizers  Finalizer has been inited
  Normal  Updated          2s    initFinalizers  Successfully update finalizer of resource
  Normal  Updated          2s    desiredphase    Successfully update desiredPhase of resource
  Normal  Applied          2s    records         Successfully apply chaos for online-boutique/productcatalogservice-c4cfd98fb-zm88k
  Normal  Updated          2s    records         Successfully update records of resource
```
```text
cleanup: deleted PodChaos online-boutique-productcatalog-pod-kill
```