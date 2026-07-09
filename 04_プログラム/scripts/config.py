# ===== 座標系 =====
CRS_WGS84   = "EPSG:4326"   # 入出力・folium可視化用
CRS_JGD2011 = "EPSG:6668"   # 空間演算の基準CRS（A31a GML準拠）
CRS_JGD2000 = "EPSG:4612"   # P20 Shapefile のCRS

# ===== 対象地域 =====
JOSO_PLACE = "常総市, 茨城県, 日本"
JOSO_BBOX  = (139.90, 36.00, 140.10, 36.15)  # (lon_min, lat_min, lon_max, lat_max)
BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH = JOSO_BBOX
JOSO_CODE  = "08211"

# ===== 浸水閾値 =====
FLOOD_DEPTH_THRESHOLD = 2      # waterDepth コード値（A31a） >= 2 = 0.5m以上
FLOOD_DEPTH_THRESHOLD_M = 0.5  # 浸水ナビ API の浸水深（m）

# ===== 道路閉鎖生成 =====
# "suiboumap_hydrograph": 浸水ナビの時刻別メッシュ深度を使用
# "kml_a31a": 従来の KML+A31a 浸水ポリゴンを使用
CLOSURE_SOURCE = "kml_a31a"
USE_CUMULATIVE_CLOSURE = True

# ===== シミュレーション時間 =====
SIM_START_EPOCH       = "2015-09-10T12:50:00"
SIM_DURATION_H        = 6
SIM_UPDATE_INTERVAL_S = 1800

# ===== KML 8時点 =====
KML_TIMESTAMPS = [
    "2015-09-10T18:00:00",
    "2015-09-11T06:00:00",
    "2015-09-11T18:00:00",
    "2015-09-12T06:00:00",
    "2015-09-12T18:00:00",
    "2015-09-13T06:00:00",
    "2015-09-13T18:00:00",
    "2015-09-16T10:20:00",
]

# ===== エージェント設定 =====
TOTAL_POPULATION      = 61_483
TOTAL_HOUSEHOLDS      = 23_500
ELDERLY_RATE          = 0.27
CAR_OWNERSHIP_RATE    = 0.85
NON_CAR_RATE          = 0.15  # = 1 - CAR_OWNERSHIP_RATE
HOUSEHOLD_SIZE        = 2.3
FLOOD_AREA_RATIO      = 1 / 3
FLOOD_POP_ESTIMATE    = 19_800

# ===== Phase 3 救出走行・車両会計 =====
# Base values follow P3-IMPL-0. Sensitivity candidates are kept here so
# scenario generation can vary one factor without changing formulas.
RESCUE_RATE_R              = 1.0
RESCUE_RATE_SENSITIVITY    = [0.5, 0.75, 1.0]
RESCUE_PER_VEHICLE_K       = HOUSEHOLD_SIZE
NON_CAR_RATE_SENSITIVITY   = [0.10, 0.15, 0.20]
CARS_PER_HOUSEHOLD         = 1.0
CARS_PER_HOUSEHOLD_MAX     = 1.55
RESCUE_STOP_DURATION_S     = 60

# ===== バス設定（ベースケース） =====
BUS_COUNT_BASE       = 5
BUS_CAPACITY_STD     = 8
BUS_CAPACITY_WELFARE = 4
BUS_WELFARE_RATIO    = 0.20
BUS_SPEED_KMH        = 20
BUS_ONEWAY_KM        = 5
BUS_BOARDING_MIN     = 5
BUS_SENSITIVITY      = [3, 5, 10]

# ----- シナリオB実装用の派生・追加定数（2026-07-07・_シナリオB実装仕様_fable5.md） -----
# SUMO の vType/stop にそのまま渡すため、既存ベース値から派生させる（DRY）。
BUS_MAXSPEED_MS       = round(BUS_SPEED_KMH * 1000 / 3600, 2)  # 20km/h → 5.56 m/s
BUS_BOARDING_TIME_S   = BUS_BOARDING_MIN * 60                  # 乗車/降車の停車時間 300s
# 需要枯渇でも最低1台の福祉車両を確保する（N=3 で round(0.2*3)=1、境界の明示保証）。
BUS_WELFARE_MIN_COUNT = 1
# busStop の敷設長（lane 上での占有長）。lane 長不足時はこの範囲で収める。
BUS_STOP_LENGTH_M     = 15.0
# ルート repeat の上限回数（理論最大約9往復を確実に上回る値。6時間で自然打切り）。
BUS_ROUTE_REPEAT_MAX  = 14

# ===== 道路ネットワーク =====
OSM_NETWORK_TYPE = "drive"

# ===== ファイルパス（scripts/ からの相対パス） =====
DATA_DIR   = "../data"
OUTPUT_DIR = "../output"

KML_DIR   = f"{DATA_DIR}/flood_kml/D1-No917_joso"
GML_DIR   = f"{DATA_DIR}/flood_hazard_a31/A31a-24_08_10_GML"
FLOOD_KML_DIR = KML_DIR
A31a_GML_DIR = GML_DIR
# 予約定数（現行実装では未使用）。実装仕様書の通り河川コードによる絞り込みは行わず、
# N03常総市境界クリップで地理的に限定する。
KINUGAWA_RIVER_NUMBER = "8303030018"
MESH_FILE = (
    f"{DATA_DIR}/population_mesh"
    "/5歳階級別人口250メッシュ_茨城/tblT001178Q08.txt"
)
SHELTER_SHP_PATH = (
    f"{DATA_DIR}/shelters"
    "/避難施設データ_茨城/P20-12_08.shp"
)
SHELTER_DBF = (
    f"{DATA_DIR}/shelters"
    "/避難施設データ_茨城/P20-12_08.dbf"
)
# GSI 緊急避難場所（2号・2026年版）― 洪水フラグ付き・全44市区町村対応
GSI_SHELTERS_2_CSV = (
    f"{DATA_DIR}/shelters"
    "/gsi_designated_shelters_ibaraki_20260331"
    "/08000_2_designated_emergency_evacuation_sites.csv"
)
# A31a 都道府県管理河川（08_20）
A31a_GML_DIR_20 = f"{DATA_DIR}/flood_hazard_a31/A31a-24_08_20_GML"
N03_SHP_PATH = (
    f"{DATA_DIR}/admin_boundary"
    "/N03-150101_08_GML/N03-20150101_08_GML/N03-15_08_150101.shp"
)
SUIBOUMAP_HYDROGRAPH_PATH = (
    f"{DATA_DIR}/suiboumap/hydrograph_origins_BP030.json"
)

# ===== 出力パス =====
OUT_NETWORK_DIR = f"{OUTPUT_DIR}/network"
OUT_CITIES_NETWORK_DIR = f"{OUTPUT_DIR}/network/cities"
OUT_SCENARIO_CITIES_DIR = f"{OUTPUT_DIR}/scenario_cities"
OUT_FLOOD_DIR   = f"{OUTPUT_DIR}/flood"
OUT_CLOSURE_DIR = f"{OUTPUT_DIR}/closure"
OUT_AGENTS_DIR  = f"{OUTPUT_DIR}/agents"
OUT_ROUTES_DIR  = f"{OUTPUT_DIR}/routes"
OUT_RESULTS_DIR = f"{OUTPUT_DIR}/results"

GRAPHML_PATH     = f"{OUT_NETWORK_DIR}/joso_road_network.graphml"
EDGES_GPKG_PATH  = f"{OUT_NETWORK_DIR}/joso_edges.gpkg"
NETWORK_MAP_PATH = f"{OUT_NETWORK_DIR}/joso_network_map.html"

FLOOD_PKL_PATH = f"{OUT_FLOOD_DIR}/flood_polygons.pkl"
FLOOD_MAP_PATH = f"{OUT_FLOOD_DIR}/flood_timeline_map.html"

CLOSURE_PKL_PATH  = f"{OUT_CLOSURE_DIR}/closure_dict.pkl"
CLOSURE_JSON_PATH = f"{OUT_CLOSURE_DIR}/road_closure_timeline.json"
CLOSURE_CSV_PATH  = f"{OUT_CLOSURE_DIR}/road_closure_timeline.csv"
CLOSURE_DIAGNOSTICS_CSV_PATH = f"{OUT_CLOSURE_DIR}/closure_diagnostics.csv"

ORIGINS_CSV_PATH  = f"{OUT_AGENTS_DIR}/origin_points.csv"
SHELTERS_CSV_PATH = f"{OUT_AGENTS_DIR}/shelters.csv"
UNREACHABLE_PATH  = f"{OUT_ROUTES_DIR}/unreachable_agents.csv"
