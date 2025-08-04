import click
from flask import current_app
from werkzeug.security import generate_password_hash
import os
import httpx

@click.command("create-manager")
@click.argument("username")
@click.argument("email")
@click.argument("password")
def create_manager(username, email, password):
    """Create a manager user in Supabase via CLI."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        click.echo("Supabase credentials not set in environment.")
        return

    password_hash = generate_password_hash(password)
    payload = {
        "username": username,
        "email": email,
        "password_hash": password_hash,
    }
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    # Insert into Supabase
    response = httpx.post(
        f"{supabase_url}/rest/v1/manager",
        json=[payload],
        headers=headers
    )
    # The above code sends a POST request to Supabase REST API to insert the manager data.
    # If the Supabase table and API key are set up correctly, the data will be saved in Supabase.
    if response.status_code in (200, 201):
        click.echo("Manager created successfully.")
    else:
        click.echo(f"Error: {response.text}")
