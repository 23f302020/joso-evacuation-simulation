# ===== 座標系 =====
CRS_WGS84   = "EPSG:4326"   # 入出力・folium可視化用
CRS_JGD2011 = "EPSG:6668"   # 空間演算の基準CRS（A31a GML準拠）
CRS_JGD2000 = "EPSG:4612"   # P20 Shapefile のCRS

# ===== 対象地域 =====
JOSO_PLACE = "常総市, 茨城県, 日本"
JOSO_BBOX  = (139.90, 36.00, 140.10, 36.15)  # (lon_min, lat_min, lon_max, lat_max)
JOSO_CODE  = "08211"

# ===== 浸水閾値 =====
FLOOD_DEPTH_THRESHOLD = 2      # waterDepth コード値（A31a） >= 2 = 0.5m以上
FLOOD_DEPTH_THRESHOLD_M = 0.5  # 浸水ナビ API の浸水深（m）

# ===== 道路閉鎖生成 =====
# "suiboumap_hydrograph": 浸水ナビの時刻別メッシュ深度を使用
# "kml_a31a": 従来の KML+A31a 浸水ポリゴンを使用
CLOSURE_SOURCE = "suiboumap_hydrograph"
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
FLOOD_AREA_RATIO      = 1 / 3
FLOOD_POP_ESTIMATE    = 19_800

# ===== バス設定（ベースケース） =====
BUS_COUNT_BASE       = 5
BUS_CAPACITY_STD     = 8
BUS_CAPACITY_WELFARE = 4
BUS_WELFARE_RATIO    = 0.20
BUS_SPEED_KMH        = 20
BUS_ONEWAY_KM        = 5
BUS_BOARDING_MIN     = 5
BUS_SENSITIVITY      = [3, 5, 10]

# ===== 道路ネットワーク =====
OSM_NETWORK_TYPE = "drive"

# ===== ファイルパス（scripts/ からの相対パス） =====
DATA_DIR   = "../data"
OUTPUT_DIR = "../output"

KML_DIR   = f"{DATA_DIR}/flood_kml"
GML_DIR   = f"{DATA_DIR}/flood_hazard_a31/A31a-24_08_10_GML"
MESH_FILE = (
    f"{DATA_DIR}/population_mesh"
    "/5歳階級別人口250メッシュ_茨城/tblT001178Q08.txt"
)
SHELTER_DBF = (
    f"{DATA_DIR}/shelters"
    "/避難施設データ_茨城/P20-12_08.dbf"
)
SUIBOUMAP_HYDROGRAPH_PATH = (
    f"{DATA_DIR}/suiboumap/hydrograph_origins_BP030.json"
)

# ===== 出力パス =====
OUT_NETWORK_DIR = f"{OUTPUT_DIR}/network"
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
