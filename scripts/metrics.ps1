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
WITH "$pd1" as pd1, "$pd2" as pd2

// Find all accessible resources
MATCH (:PD {PD_ID: pd1})-[:HAS_ACCESS_TO|MAP*1..4]->(r1:Resource)
WITH pd2, COLLECT(DISTINCT r1) as r1
MATCH (:PD {PD_ID: pd2})-[:HAS_ACCESS_TO|MAP*1..4]->(r2:Resource)
WITH r1, COLLECT(DISTINCT r2) as r2

// Split by type
WITH r1, r2, ["VMR","PMR","PCPU","FILE","BLOCK","ADS","MO","VCPU"] AS types
WITH [t IN types | [n in r1 WHERE n.RES_TYPE = t] ] as r1, [t IN types | [n in r2 WHERE n.RES_TYPE = t] ] as r2 
WITH r1, r2, apoc.coll.zip(r1, r2) as r_zip

// Intersection
WITH r1, r2, [entry in r_zip | apoc.coll.intersection(entry[0], entry[1])] as inter

// Counts
WITH [t in r1 | size(t)] as c1, [t in r2 | size(t)] as c2, [t in inter | size(t)] as cI

return {c1: c1, c2: c2, cI:cI}
"@

$result = Exec-Query -cypherQuery $rsiQuery
Write-Output "$result"

# Process the output string
$parts = $result -split ': '

# Extract the last three parts as string arrays
$counts1 = $parts[-1] -replace '(\[|\].*)', '' -split ','
$counts_intersect = $parts[-2] -replace '(\[|\].*)', '' -split ','
$counts2 = $parts[-3] -replace '(\[|\].*)', '' -split ','

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