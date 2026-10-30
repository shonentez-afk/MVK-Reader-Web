/* Stage111Z.5: source-derived synthetic x87 Hann table probe (offline only).
 * Source code is independent research. Original Delphi EXE/IDP/TSXML/RAW/BIN
 * are neither read nor embedded. This is NOT authenticated Delphi runtime.
 *
 * Original private-IDP structure (verified separately, not distributed):
 * 008C1064: initialize 262144 f32 Hann samples under runtime x87 CW;
 *            fild index, 80-bit 2*pi, fmul, fdiv 262144f, FCOS,
 *            1-cos, FSQRT(1.5L), divide, FSTP Single.
 * 007D2044..007D2080: index_stride = 262144/N, sample *= table[i*stride].
 */
#include <float.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#if !defined(__GNUC__) || !(defined(__x86_64__) || defined(__i386__))
#error "GNU x86/x86_64 with native x87 is required"
#endif
#if LDBL_MANT_DIG != 64
#error "requires 80-bit extended long double"
#endif

#define HANN_LENGTH 262144u
static const long double TWO_PI =
    6.2831853071795864769252867665590057683943387987502116L;
static const long double ONE_POINT_FIVE = 1.5L;
static const float FFT_TABLE_SIZE_SINGLE = 262144.0f;

static float source_hann_sample(uint32_t index) {
    const int32_t i = (int32_t)index;
    long double angle, numerator;
    float result;
    /* GAS AT&T fsubp/fdivp below encode Intel DE E1/DE F1 (FSUBRP/FDIVRP)
     * respectively; we check the sign and roundtrip in synthetic tests.
     * The explicit FSTP/F-LD TBYTE reproduce original Extended temp stores.
     */
    __asm__ volatile(
        "fildl %[i]\n\t"
        "fldt %[two_pi]\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fdivs %[n]\n\t"
        "fstpt %[angle]\n\t"
        "fldt %[angle]\n\t"
        "fcos\n\t"
        "fwait\n\t"
        "fld1\n\t"
        "fsubp %%st, %%st(1)\n\t"
        "fstpt %[num]\n\t"
        "fldt %[one_half]\n\t"
        "fsqrt\n\t"
        "fldt %[num]\n\t"
        "fdivp %%st, %%st(1)\n\t"
        "fstps %[out]"
        : [out] "=m" (result), [angle] "=&m" (angle),
          [num] "=&m" (numerator)
        : [i] "m" (i), [two_pi] "m" (TWO_PI),
          [n] "m" (FFT_TABLE_SIZE_SINGLE),
          [one_half] "m" (ONE_POINT_FIVE)
        : "st"
    );
    return result;
}

static uint32_t float_bits(float v) {
    uint32_t bits = 0;
    memcpy(&bits, &v, sizeof(bits));
    return bits;
}

int main(int argc, char **argv) {
    int summary = argc == 2 && strcmp(argv[1], "--summary") == 0;
    int hex_all = argc == 2 && strcmp(argv[1], "--hex-all") == 0;
    if (!summary && !hex_all) {
        fputs("usage: x87_hann_table_probe --summary|--hex-all\n", stderr);
        return 2;
    }
    const uint32_t selected[] = {0, 1, 2, 3, 5, 8192, 16384, 32768,
                                 65536, 131072, 196608, 262139, 262142, 262143};
    uint32_t observed[sizeof(selected)/sizeof(selected[0])];
    unsigned short original = 0, cw = 0, restored = 0;
    const unsigned short static_initial = 0x1332u;
    uint64_t checksum = UINT64_C(14695981039346656037);
    __asm__ volatile("fnstcw %0" : "=m"(original));
    __asm__ volatile("fldcw %0" :: "m"(static_initial));
    __asm__ volatile("fnstcw %0" : "=m"(cw));
    /* Follow original in all entries and keep stdout bounded in summary mode.
     * Control-word change is local to this invocation and always restored. */
    unsigned next_selected = 0;
    for (uint32_t index = 0; index < HANN_LENGTH; ++index) {
        const uint32_t bits = float_bits(source_hann_sample(index));
        if (summary && next_selected < sizeof(selected)/sizeof(selected[0]) &&
            index == selected[next_selected]) {
            observed[next_selected++] = bits;
        }
        if (hex_all) printf("%08" PRIX32 "\n", bits);
        for (unsigned b = 0; b < 4; ++b) {
            checksum ^= (bits >> (b * 8)) & 0xFFu;
            checksum *= UINT64_C(1099511628211);
        }
    }
    __asm__ volatile("fnclex\n\tfldcw %0" :: "m"(original));
    __asm__ volatile("fnstcw %0" : "=m"(restored));
    if ((cw & (unsigned short)~0x0040u) != static_initial ||
        restored != original) {
        fputs("x87 CW initialization or restoration failed\n", stderr);
        return 3;
    }
    if (summary) {
        printf("# source=STAGE111Z5_SYNTHETIC_X87_HANN initial_cw=0x%04X active_cw=0x%04X restored=1 n=%u\n",
               static_initial, cw, HANN_LENGTH);
        for (unsigned j = 0; j < sizeof(selected)/sizeof(selected[0]); ++j)
            printf("%" PRIu32 ",%08" PRIX32 "\n", selected[j], observed[j]);
        printf("# fnv64=%016" PRIX64 "\n", checksum);
    }
    return 0;
}
