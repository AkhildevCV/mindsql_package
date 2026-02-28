# schema_manager.py

from sqlalchemy import inspect
import config

def update_schema_context(engine):
    """
    Extracts live DB schema, including Primary and Foreign Keys, 
    and dynamically updates the in-memory validation map.
    """
    inspector = inspect(engine)
    schema_text = ""
    dynamic_schema_map = {}
    
    for table_name in inspector.get_table_names():
        schema_text += f"CREATE TABLE {table_name} (\n"
        columns = inspector.get_columns(table_name)
        col_names = []
        
        for i, col in enumerate(columns):
            col_names.append(col['name'])
            comma = "," if i < len(columns) - 1 else ""
            schema_text += f"    {col['name']} {col['type']}{comma}\n"
        
        schema_text += ");\n"
        
        # Extract Primary Keys
        pks = inspector.get_pk_constraint(table_name).get('constrained_columns', [])
        if pks:
            schema_text += f"-- Primary Keys: {', '.join(pks)}\n"
            
        # Extract Foreign Keys
        fks = inspector.get_foreign_keys(table_name)
        if fks:
            fk_strs = [f"({', '.join(fk['constrained_columns'])}) references {fk['referred_table']}({', '.join(fk['referred_columns'])})" for fk in fks]
            schema_text += f"-- Foreign Keys: {', '.join(fk_strs)}\n"
            
        schema_text += "\n"
        dynamic_schema_map[table_name] = col_names
        
    # Overwrite the stale schema file on the disk
    with open(config.SCHEMA_FILE, 'w') as f:
        f.write(schema_text)
        
    # Dynamically update the config map in memory
    config.SCHEMA_MAP.clear()
    config.SCHEMA_MAP.update(dynamic_schema_map)
        
    return schema_text