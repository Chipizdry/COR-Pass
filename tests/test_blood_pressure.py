import asyncio
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cor_pass.database.models.user import User


@pytest.mark.asyncio
async def test_create_bp_measurement_success(authorized_client: AsyncClient):
    url = "/api/measurements/blood_pressure/"
    measured_at = datetime.utcnow().replace(microsecond=0).isoformat()
    payload = {
        "systolic_pressure": 120,
        "diastolic_pressure": 80,
        "pulse": 70,
        "measured_at": measured_at,
    }

    resp = await authorized_client.post(url, json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["systolic_pressure"] == 120
    assert data["diastolic_pressure"] == 80
    assert data["pulse"] == 70
    assert "id" in data and isinstance(data["id"], str)
    assert "user_id" in data and isinstance(data["user_id"], str)
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_my_measurements_sorted_desc(authorized_client: AsyncClient):
    base_url = "/api/measurements/blood_pressure/"

    # Create three measurements with different measured_at
    now = datetime.utcnow().replace(microsecond=0)
    bodies = [
        {"systolic_pressure": 110, "diastolic_pressure": 70, "pulse": 60, "measured_at": (now - timedelta(hours=2)).isoformat()},
        {"systolic_pressure": 115, "diastolic_pressure": 75, "pulse": 65, "measured_at": (now - timedelta(hours=1)).isoformat()},
        {"systolic_pressure": 118, "diastolic_pressure": 78, "pulse": 68, "measured_at": now.isoformat()},
    ]

    for body in bodies:
        r = await authorized_client.post(base_url, json=body)
        assert r.status_code == 201, r.text

    # Fetch my measurements
    resp = await authorized_client.get("/api/measurements/blood_pressure/my")
    assert resp.status_code == 200, resp.text
    items = resp.json()

    assert len(items) >= 3

    # Ensure sorted by measured_at desc
    measured_at_list = [datetime.fromisoformat(i["measured_at"]) for i in items]
    assert measured_at_list == sorted(measured_at_list, reverse=True)


@pytest.mark.asyncio
async def test_get_measurements_paginated_all(
    authorized_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    # Ensure test_user has a cor_id to query by patient_cor_id
    test_user.cor_id = "TEST_COR_001"
    db_session.add(test_user)
    await db_session.commit()

    now = datetime.utcnow().replace(microsecond=0)

    # Create 12 measurements via API for the current user
    for i in range(12):
        body = {
            "systolic_pressure": 100 + i,
            "diastolic_pressure": 60 + i,
            "pulse": 55 + i,
            "measured_at": (now - timedelta(minutes=i)).isoformat(),
        }
        r = await authorized_client.post("/api/measurements/blood_pressure/", json=body)
        assert r.status_code == 201, r.text

    # Request page 2, page_size 5
    params = {
        "patient_cor_id": test_user.cor_id,
        "page": 2,
        "page_size": 5,
        "period": "all",
    }
    resp = await authorized_client.get("/api/measurements/blood_pressure/list", params=params)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["page"] == 2
    assert data["page_size"] == 5
    assert data["total"] >= 12
    assert len(data["items"]) == 5

    # Items should be ordered by measured_at desc
    items = data["items"]
    measured_ats = [datetime.fromisoformat(i["measured_at"]) for i in items]
    assert measured_ats == sorted(measured_ats, reverse=True)


@pytest.mark.asyncio
async def test_get_measurements_patient_not_found(authorized_client: AsyncClient):
    params = {
        "patient_cor_id": "UNKNOWN_COR_ID",
        "page": 1,
        "page_size": 5,
        "period": "all",
    }
    resp = await authorized_client.get("/api/measurements/blood_pressure/list", params=params)
    assert resp.status_code == 404
    assert resp.json().get("detail") == "User/Patient not found"
