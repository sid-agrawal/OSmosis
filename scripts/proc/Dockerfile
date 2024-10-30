# use neo4j:community for latest version, 5.22.0 is known working version
FROM neo4j:5.22.0

# marks these directories as mounted from host
VOLUME [ "/data/", "/import/", "/plugins/" ]

# ports neo4j listens on: 7474 is the web browser, 7687 is the Cypher port
EXPOSE 7474 7687

ENV NEO4J_AUTH=neo4j/password

# plugin required for import script
ENV NEO4J_apoc_export_file_enabled=true
ENV NEO4J_apoc_import_file_enabled=true
ENV NEO4J_apoc_import_file_use__neo4j__config=true
ENV NEO4J_PLUGINS=\[\"apoc\"\]
