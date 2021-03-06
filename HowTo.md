# DBLinker out-of-the-box use

By default, the DBLinker uses a PostgreSQL database with a specific structure. This section gives some general details about the script and describes how to use it in this configuration.

## What can I do with Python DBLinker?
You can generate 3D scenes from 2D spatial vectors and run simulations on them using [CitySim solver](https://www.epfl.ch/labs/leso/transfer/software/citysim/). The script uses multithreading to speed up the process.

## What do I need?
Other than the script itself, you need a PostgreSQL database with PostGIS installed, a climate file and CitySim solver.

## What's the structure of the PostgreSQL database?
The structure of the database is made up of 4 schemas:
<br />
<br />  
![db_schemas](https://github.com/rboghe/PythonDatabaseLinker/blob/master/images/schemas.png?raw=true)
*_This table will be created or updated by the script if needed_
<br />
<br />
The first schema, city, contains the geometrical information needed to create the scene and the general features of the buildings.
