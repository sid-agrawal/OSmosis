<# 
Calculate the RSI / FRI metrics for a pair of PDs 
Example usage: ./metrics 'PD_4.0' 'PD_4.1'
#>

$pd1=$args[0]
$pd2=$args[1]

# Load variables
Get-Content config.txt | Foreach-Object{
   $var = $_.Split('=')
   New-Variable -Name $var[0] -Value $var[1]
}

# Constants
$types = @("VMR","PMR","PCPU","FILE","BLOCK","ADS","MO","VCPU") # resource types

# Helper functions
function Exec-Query {
    param(
        [string]$cypherQuery
    )

    $prevPwd = ($pwd).path
    & cd $cypherExePath

    $cypherQueryFile = "tempfile.cypher"
    Set-Content -Path $cypherQueryFile -Value $cypherQuery

    $command = "./cypher-shell -a $neo4jServer -u $neo4jUsername -p $neo4jPassword -f $cypherQueryFile"
    $result = Invoke-Expression -Command $command

    & cd $prevPwd

    return $result
}

# Get RSI metric
$rsiQuery = @"
// Define the starting nodes
WITH "$pd1" as pd1, "$pd2" as pd2
MATCH (startNode1:PD {PD_ID: pd1}), (startNode2:PD {PD_ID: pd2})
WITH startNode1, startNode2

// First BFT from startNode1
CALL apoc.path.expandConfig(startNode1, {
    relationshipFilter: "HAS_ACCESS_TO>|MAP>",
    labelFilter: "Resource",
    filterStartNode: false,
    algorithm: "BFS",
    maxLevel : 4
}) YIELD path as pathrr1

// Collect nodes from the first BFT
WITH startNode2, collect(DISTINCT nodes(pathrr1)) as nodes1

// Second BFT from startNode2
CALL apoc.path.expandConfig(startNode2, {
    relationshipFilter: "HAS_ACCESS_TO>|MAP>",
    labelFilter: "Resource",
    filterStartNode: false,
    algorithm: "BFS",
    maxLevel : 4
}) YIELD path as pathrr2

// Collect nodes from the second BFT
WITH nodes1, collect(DISTINCT nodes(pathrr2)) as nodes2

// nodes1 and nodes2 are nested arrays, so
UNWIND nodes1 as uw_nodes1
UNWIND nodes2 as uw_nodes2

// filter out PD nodes
WITH [n in uw_nodes1 WHERE n:Resource] as res1, [n in uw_nodes2 WHERE n:Resource] as res2
UNWIND res1 as uw_res1
UNWIND res2 as uw_res2

WITH collect(DISTINCT uw_res1) as res1, collect(DISTINCT uw_res2) as res2, ["VMR","PMR","PCPU","FILE","BLOCK","ADS","MO","VCPU"] AS types
WITH [t IN types | [n in res1 WHERE n.RES_TYPE = t] ] as res1_by_type, [t IN types | [n in res2 WHERE n.RES_TYPE = t] ] as res2_by_type 
WITH res1_by_type, res2_by_type, apoc.coll.zip(res1_by_type, res2_by_type) as res_zipped

// intersection
WITH res1_by_type, res2_by_type, [entry in res_zipped | apoc.coll.intersection(entry[0], entry[1])] as intersection_by_type

// counts
WITH [t in res1_by_type | size(t)] as counts1, [t in res2_by_type | size(t)] as counts2, [t in intersection_by_type | size(t)] as counts_intersect

return {counts1: counts1, counts2: counts2, counts_intersect:counts_intersect}
"@

$result = Exec-Query -cypherQuery $rsiQuery
Write-Output "$result"

# Process the output string
$parts = $result -split ': '

# Extract the last three parts as string arrays
$counts1 = $parts[-1] -replace '(\[|\].*)', '' -split ','
$counts2 = $parts[-2] -replace '(\[|\].*)', '' -split ','
$counts_intersect = $parts[-3] -replace '(\[|\].*)', '' -split ','

# Convert the extracted strings to arrays of integers
$counts1 = $counts1 | ForEach-Object { [int]$_ }
$counts2 = $counts2 | ForEach-Object { [int]$_ }
$counts_intersect = $counts_intersect | ForEach-Object { [int]$_ }

# Calculate the RSIs from counts
for ($i = 0; $i -lt $types.Length; $i++) {
    $type = $types[$i]
    $rsi1 = if ($counts1[$i] -gt 0) {$counts_intersect[$i] / $counts1[$i]} Else {0}
    $rsi2 = if ($counts2[$i] -gt 0) {$counts_intersect[$i] / $counts2[$i]} Else {0}
    $rsi = [Math]::Max($rsi1, $rsi2)

    # Process or display elements from all arrays
    Write-Output "RSI $type : $rsi"
}

# Calculate FRI
$types = @("FILE","ADS","MO","CPU") # resource types for FRI

foreach ($type in $types) {
    $friQuery = @"
// Define the starting nodes and type
WITH "$pd1" as pd1, "$pd2" as pd2, "$type" as type

// Follow type edge by 1
MATCH (:PD {PD_ID: pd1})-[{TYPE: type}]->(ancestor1:PD)
MATCH (:PD {PD_ID: pd2})-[{TYPE: type}]->(ancestor2:PD)

// Find all paths to a shared ancestor
MATCH p1=((ancestor1)-[*0..3]->(ancestor:PD))
MATCH p2=((ancestor2)-[*0..3]->(ancestor:PD))

// Combine the paths
WITH collect(p1)+collect(p2) as p
UNWIND p as p_uw

// Get the length of the shortest one
RETURN (length(p_uw) + 1)
ORDER BY length(p_uw)
LIMIT 1
"@

$result = Exec-Query -cypherQuery $friQuery
Write-Output "FRI $type : $result"
}