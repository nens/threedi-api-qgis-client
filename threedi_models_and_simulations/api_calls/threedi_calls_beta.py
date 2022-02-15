import hashlib
from threedi_api_client.files import upload_file
from threedi_calls import get_api_client, ThreediCalls


if __name__ == "__main__":
    api_client = get_api_client(
        api_username="lukasz.debek",
        api_password="F4e61d2160daf058ae690102141bcc4F",
        api_host="https://api.staging.3di.live",
    )
    name = "Grevelingen_clean2"
    owner = "b08433fa47c1401eb9cbd4156034c679"
    owner_name = "N&S IT"
    sqlite_filename = "grevelingen.sqlite"
    raster_name = "dem_grevelingen.tif"
    waterlevel_raster_name = "initial_waterlevel.tif"
    sqlite_path = r"C:\D\GIS\3Di\Grevelingen\grevelingen.sqlite"
    raster_path = r"C:\D\GIS\3Di\Grevelingen\rasters\dem_grevelingen.tif"
    waterlevel_raster_path = r"C:\D\GIS\3Di\Grevelingen\rasters\initial_waterlevel.tif"
    tc = ThreediCalls(api_client)
    print(api_client)

    print(tc.fetch_3di_models_with_count(limit=tc.FETCH_LIMIT, schematisation_name="Grevelingen", show_invalid=True))
    # print(tc.threedi_api.repositories_list)
    # print(tc.fetch_schematisation(4))
    # print(tc.fetch_schematisation_revisions(8))
    # print(tc.create_schematisation(name, owner))
    # print(tc.fetch_schematisations())
    # print(tc.fetch_schematisation_latest_revision(11))
    # print(tc.create_schematisation_revision(8))

    # r = tc.fetch_schematisation_revision(8, 2892)
    # print(r)
    # with open(raster_path, "rb") as file_to_check:
    #     data = file_to_check.read()
    #     md5_returned = hashlib.md5(data).hexdigest()
    #     print(md5_returned)

    # print(tc.delete_schematisation_revision_sqlite(8, 2855))
    # up = tc.upload_schematisation_revision_sqlite(8, 2856, sqlite_filename)
    # upload_file(up.put_url, sqlite_path, 1024, callback_func=lambda x, y: print(x, y))
    # print(tc.create_schematisation_revision_raster(8, 2856, raster_name))
    # rup = tc.upload_schematisation_revision_raster(7, 8, 2856, raster_name)
    # upload_file(rup.put_url, raster_path, 1024, callback_func=lambda x, y: print(x, y))
    # print(tc.create_schematisation_revision_raster(8, 2856, waterlevel_raster_name, raster_type="initial_waterlevel_file"))
    # wrup = tc.upload_schematisation_revision_raster(8, 8, 2856, waterlevel_raster_name)
    # upload_file(wrup.put_url, waterlevel_raster_path, 1024, callback_func=lambda x, y: print(x, y))
    # print(tc.commit_schematisation_revision(8, 2856, commit_message="testing"))
    # print(tc.fetch_schematisation_revision_tasks(8, 2856))

    # print(tc.create_schematisation_revision_3di_model(8, 2856, **r.to_dict()))
