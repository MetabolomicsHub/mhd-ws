# mhd-ws
Metabolomics Hub submission and search web services

# Development & Test Environment

To run and test Metabolomics Hub server, you have to install [docker-compose tool](https://docs.docker.com/compose/install/).

You can run Metabolomics Submission Server with this commands.
```
mv config.example.yaml config.yaml
mv config-secrets.example.yaml config-secrets.yaml
mkdir -p db_data
docker-compose up
```


```
Open http://localhost:7070 on your browser to access Rest API endpoints
or
Open http://localhost:7070/docs on your browser to find Rest API documentation
```

Example API TOKEN
```
mhd_1781097016_1d81aa35-4896-44bc-8dee-a0198e88b2a8
```

Example JWT TOKEN
```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJNZXRhYm9MaWdodHMiLCJhdWQiOiJodHRwczovL3d3dy5tZXRhYm9sb21pY3NodWIub3JnIiwiaWF0IjoxNjk5ODg2NTAwLCJleHAiOjE4OTk5NzI5MDB9.h9hNPcrh8aekGplPdLtvgkEzwPjUBb1TA8TVV-2pBdTofySS2dDsiW_e0HVVy2MqmEeuRiTpT6Wrc2U3XAnEmchy-58Md-UeIdVSNd1F6NW7z2ysHIG_j_g5_sJ4AIHH6U4fHmc8P7mXT8QO9jLU2XLkZ5RCoSioxkpPMjRjmvNr3ugBlDjr13jm-yEcvzdCFq4s4soypnmaYKBZv6ycvcOfb_q6a7qI_w3BQ2ii5kGND5t94VNwxLMF7IqcKlLtVKutD2D1PZKS_bdEu817_oIw8dSqzI00mJBDHjD5rszDkF_9UZAAKb_VxArBewZP955uwpz4t_lackqUs2tXww
```
