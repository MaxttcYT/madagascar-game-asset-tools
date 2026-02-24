#pragma pack(push,1)

/* ==== Top-level file ==== */
/* 0x00 */
typedef struct {
    uint32_t id;          /* 0x0000080D */
    uint32_t file_size;   /* size excluding first 0x0C bytes */
    uint32_t version;     /* RW version */
    /* followed by chunks */
} RWS_FileHeader;


/* ==== Generic RenderWare chunk ==== */
typedef struct {
    uint32_t id;          /* chunk id */
    uint32_t size;        /* chunk payload size */
    uint32_t version;     /* RW version */
} RWS_ChunkHeader;


/* ==== Audio header chunk (0x0000080E) ==== */
typedef struct {
    uint32_t header_size_actual;
    uint32_t section_size_1;
    uint32_t section_size_2;
    uint32_t section_size_3;
    uint32_t config_1;
    uint32_t config_2;
    uint32_t zero_1;

    uint32_t total_segments;
    uint32_t config_3;
    uint32_t total_layers;
    uint32_t config_4;

    uint32_t unknown_30;
    uint32_t block_layers_size;
    uint32_t data_offset;
    uint32_t zero_2;

    uint8_t  file_uuid[16];

    /* followed by padded string: file name */
} RWS_HeaderBase;


/* ==== Segment info table (count = total_segments) ==== */
typedef struct {
    uint32_t unk_00;
    uint32_t unk_04;
    uint32_t unk_08;
    uint32_t unk_0C;
    uint32_t unk_10;
    uint32_t unk_14;
    uint32_t layers_size;     /* total size of all layers incl padding */
    uint32_t data_offset;     /* offset inside data chunk */
} RWS_SegmentInfo;


/* ==== Layer info table (count = total_layers) ==== */
typedef struct {
    uint32_t unk_00;
    uint32_t unk_04;
    uint32_t zero_08;
    uint32_t frame_hint;      /* samples/frame related */
    uint32_t block_size_pad;  /* per-layer padded block size */
    uint32_t unk_14;

    uint16_t interleave;
    uint16_t frame_size;

    uint32_t unk_1C;
    uint32_t block_size;      /* without padding */
    uint32_t layer_start;     /* offset relative to segment */
} RWS_LayerInfo;


/* ==== Layer config table (count = total_layers) ==== */
typedef struct {
    uint32_t sample_rate;
    uint32_t unk_04;
    uint32_t approx_size;
    uint16_t bits_per_sample;
    uint8_t  channels;
    uint8_t  unk_0F;

    uint32_t unk_10;
    uint32_t unk_14;
    uint32_t unk_18;

    uint32_t codec_uuid_first; /* first 32 bits of UUID */
    uint8_t  codec_uuid_rest[12];
} RWS_LayerConfig;


/* ==== Extra DSP info (only when codec == DSP) ==== */
typedef struct {
    uint32_t approx_samples;
    uint32_t unk_04;
    uint8_t  reserved[0x14];

    int16_t  coefs[16];       /* DSP coefficients */
    int16_t  hist[16];        /* initial history */
} RWS_DSPInfo;


/* ==== Data chunk (0x0000080F) ==== */
typedef struct {
    /* audio block data follows */
    uint8_t data[];
} RWS_DataChunk;

#pragma pack(pop)