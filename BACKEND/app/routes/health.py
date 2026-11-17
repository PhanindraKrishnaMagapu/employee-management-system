
"""Health-check API endpoints."""

import sqlite3

from flask import Blueprint, current_app, jsonify

from app.db import get_connection


health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Check API and database availability."""

    try:
        connection = get_connection()

        try:
            connection.execute("SELECT 1")
        finally:
            connection.close()

        return jsonify({
            "success": True,
            "message": "Employee Management System API is running",
            "database": "connected"
        }), 200

    except (sqlite3.Error, OSError) as error:
        current_app.logger.error("Health check failed: %s", error)

        return jsonify({
            "success": False,
            "message": "Database connection failed",
            "database": "disconnected"
        }), 503
