<# 
Import an OSmosis model state CSV hosted on GDrive to an AuraDB instance 
Example usage: ./import_csv 1
#>

$csvIdx=$args[0]

# Load variables
Get-Content config.txt | Foreach-Object{
   $var = $_.Split('=')
   New-Variable -Name $var[0] -Value $var[1]
}

# Public CSV file for upload
$gdriveUrls = @("",
"https://drive.google.com/uc?export=download&id=18x8W0HIMJhkRw3YRZzGMLD1gYYPG9Rpe", # 1
"https://drive.google.com/uc?export=download&id=12n97Zlo4UNkt7T9tx9ePlkmn6pw72NLS", # 2
"https://drive.google.com/uc?export=download&id=1K-qNGXI1uafKqMPt4bDNTBhH3DEZ7DYy", # 3
"https://drive.google.com/uc?export=download&id=1pY6ftNAMiShIq2CgurVbmxPgredawu-g", # 4
"https://drive.google.com/uc?export=download&id=1X3648_Tq0VAw-UVVnwOqMRsZ7el0aVMV", # 5
"https://drive.google.com/uc?export=download&id=19dMy4GliWwS39JIkyjQktUC7_PKie2fw", # 6 (5 processed)
"", # 7
"", # 8
"https://drive.google.com/uc?export=download&id=15GAXDa-tdVLH7b7xfb1iIp8iFgzBL-bn", # 9
"")

$gdriveUrl = $gdriveUrls[$csvIdx]

# Define Cypher query
$cypherQuery = @"
MATCH (n) 
DETACH DELETE n;

// Load PD nodes
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.PD_ID IS NOT NULL
MERGE (pd:PD {PD_ID: row.PD_ID, PD_NAME: row.PD_NAME});

// Load Resource nodes
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.RES_ID IS NOT NULL
MERGE(r:Resource {RES_ID: row.RES_ID, RES_TYPE: row.RES_TYPE, COMMENT: coalesce(row.CONSTRAINTS, "N/A")});

// Load PD->PD relations (RDE)
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.PD_FROM IS NOT NULL AND row.PD_TO IS NOT NULL
MATCH (pdfrom:PD {PD_ID: row.PD_FROM})
MATCH (pdto:PD {PD_ID: row.PD_TO})
CALL apoc.create.relationship(pdfrom, ("REQUESTS_" + row.RES_TYPE + "_" + row.CONSTRAINTS), {TYPE:row.RES_TYPE, CONSTRAINT:coalesce(row.CONSTRAINTS, "N/A")}, pdto) YIELD rel
RETURN rel;

// Load PD->Resource relations
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.PD_FROM IS NOT NULL AND row.RESOURCE_TO IS NOT NULL
MATCH (pdfrom:PD {PD_ID: row.PD_FROM})
MATCH (resto:Resource {RES_ID: row.RESOURCE_TO})
MERGE (pdfrom)-[:HAS_ACCESS_TO {}]-(resto);

// Load Resource->Resource map relations
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.RESOURCE_FROM IS NOT NULL AND row.RESOURCE_TO IS NOT NULL AND row.REL_TYPE = "MAP"
MATCH (resfrom:Resource {RES_ID: row.RESOURCE_FROM})
MATCH (resto:Resource {RES_ID: row.RESOURCE_TO})
MERGE (resfrom)-[:MAP {}]-(resto);
// CALL apoc.merge.relationship(resfrom, (row.REL_TYPE), {}, {}, resto, {}) YIELD rel

// Load Resource->Resource subset relations
LOAD CSV WITH HEADERS FROM '$gdriveUrl' AS row
WITH row
WHERE row.RESOURCE_FROM IS NOT NULL AND row.RESOURCE_TO IS NOT NULL AND row.REL_TYPE = "SUBSET"
MATCH (resfrom:Resource {RES_ID: row.RESOURCE_FROM})
MATCH (resto:Resource {RES_ID: row.RESOURCE_TO})
MERGE (resfrom)-[:SUBSET {}]-(resto);
"@

# Invoke command
$prevPwd = ($pwd).path
& cd $cypherExePath

$cypherQueryFile = "tempfile.cypher"
Set-Content -Path $cypherQueryFile -Value $cypherQuery

$command = "./cypher-shell -a $neo4jServer -u $neo4jUsername -p $neo4jPassword -f $cypherQueryFile"
Invoke-Expression -Command $command

& cd $prevPwd
