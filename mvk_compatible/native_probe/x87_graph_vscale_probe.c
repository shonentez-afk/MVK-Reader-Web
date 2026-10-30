/* Stage111V: pure research x87 assembly helper probe for SYNTHETIC tests.
 * Source-derived from PRIVATE IDR instruction structure; no original source
 * copied. GCC x86/x86_64 only. No network or real MVK instrument.
 * This is not certified Delphi 32-bit or original x87 control word parity.
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(__GNUC__) || !(defined(__i386__) || defined(__x86_64__))
#error "Requires GNU C with x87 on x86 or x86_64."
#endif

static long double log10_single_x87(float val) {
    long double result;
    __asm__ volatile("fldlg2\n\tflds %1\n\tfyl2x\n\tfstpt %0"
        : "=m"(result) : "m"(val) : "st");
    return result;
}

static float store_single_x87(long double val) {
    float result;
    __asm__ volatile("fldt %1\n\tfstps %0"
        : "=m"(result) : "m"(val) : "st");
    return result;
}

/* 00447DF0 noninteger exponent branch: FLDLN2, FYL2X,
 * FMLUP, FLDL2E, FRNDINT, F2XM1, FSCALE. The AT&T spelling
 * fsubr %%st,%%st(1) corresponds to Intel FSUB ST(1),ST(0).
 */
static long double x87_pow10_extended(long double exponent) {
    const long double base=10.0L;
    long double result;
    __asm__ volatile(
        "fldt %[exp]\n\t"
        "fldt %[base]\n\t"
        "fldln2\n\t"
        "fxch %%st(1)\n\t"
        "fyl2x\n\t"
        "fxch %%st(1)\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fldl2e\n\t"
        "fmulp %%st, %%st(1)\n\t"
        "fld %%st(0)\n\t"
        "frndint\n\t"
        "fsubr %%st, %%st(1)\n\t"
        "fxch %%st(1)\n\t"
        "f2xm1\n\t"
        "fld1\n\t"
        "faddp %%st, %%st(1)\n\t"
        "fscale\n\t"
        "fstp %%st(1)\n\t"
        "fstpt %[result]"
        : [result]"=m"(result) : [exp]"m"(exponent),[base]"m"(base) : "st"
    );
    return result;
}

/* Source 00447EF8 integer-power branch: exponent-by-squaring. */
static long double power_of_ten_integer(int exp) {
    uint32_t power=(uint32_t)(exp<0?-exp:exp);
    long double base=10.0L, result=1.0L;
    while(power) {
        if(power&1u) result*=base;
        power>>=1u;
        if(power) base*=base;
    }
    return exp<0?1.0L/result:result;
}

static int spectrum_graph_default_scale(float f_range, int mode,
                                        float *output, int *step_out,
                                        float *fraction_out) {
    if(!(f_range>0.0f) || !isfinite(f_range) || mode<0 || mode>3)
        return 0;
    int multiplier=(mode==2?10:(mode==3?100:1));
    float scaled=store_single_x87((long double)f_range*multiplier);
    if(!(scaled>0.0f) || !isfinite(scaled))return 0;
    long double log_val=log10_single_x87(scaled);
    long long truncval=(long long)truncl(log_val); /* @TRUNC: toward zero */
    float fraction=store_single_x87(log_val-(long double)truncval);
    /* original FUCOMPP compares frac and 0; <=0 uses +1 branch */
    int positive=(fraction>0.0f);
    float shifted=positive?fraction:store_single_x87((long double)fraction+1.0L);
    const long double threshold_two=log10_single_x87(2.0f);
    const long double threshold_five=log10_single_x87(5.0f);
    int step=shifted<threshold_two?2:(shifted<threshold_five?5:10);
    long double result;
    if(step==10) {
        /* Original uses TRUNC(LOG10(10))=1 + TRUNC(LOG10(x)) + [positive].
         * Helper 00447EF8 takes integer exponent Single and base10 Single.
         */
        int exp=(int)truncval+(positive?1:0);
        result=power_of_ten_integer(exp);
    } else {
        long double exponent=log10_single_x87((float)step)
             +(long double)truncval-(positive?0.0L:1.0L);
        result=x87_pow10_extended(exponent);
    }
    *output=store_single_x87(result);
    *step_out=step;
    *fraction_out=fraction;
    return isfinite(*output) && *output>0;
}


/* Stage111Z.2: replay one explicitly supplied Float32 FRange under an observed
 * x87 CW, using the existing source-derived arithmetic above.
 * Read-only, offline, no built-in original measurements, and NOT an original
 * Delphi oracle. A bounded input protects against unmasked CW exceptions.
 */
static uint32_t single_bits(float value) {
    uint32_t bits = 0;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

static int parse_hex_fixed(const char *input, unsigned digits, uint32_t *result) {
    uint32_t bits = 0;
    unsigned i = 0;
    for (; i < digits && input[i]; ++i) {
        const char ch = input[i];
        unsigned nibble;
        if (ch >= '0' && ch <= '9') nibble = (unsigned)(ch - '0');
        else if (ch >= 'a' && ch <= 'f') nibble = (unsigned)(ch - 'a' + 10);
        else if (ch >= 'A' && ch <= 'F') nibble = (unsigned)(ch - 'A' + 10);
        else return 0;
        bits = (bits << 4) | nibble;
    }
    if (i != digits || input[i]) return 0;
    *result = bits;
    return 1;
}

static int run_bitwise_replay(const char *f_range_hex, const char *cw_hex) {
    uint32_t raw = 0, cw_bits = 0;
    if (!parse_hex_fixed(f_range_hex, 8, &raw) ||
        !parse_hex_fixed(cw_hex, 4, &cw_bits) ||
        (cw_bits != 0x1332u && cw_bits != 0x1372u)) {
        fputs("invalid Float32 HEX or unsupported observed CW\n", stderr);
        return 2;
    }
    float f_range;
    memcpy(&f_range, &raw, sizeof(f_range));
    /* Avoid FPU traps with the original CW's unmasked exception bits. */
    if (!isfinite(f_range) || f_range < 1.0e-8f || f_range > 1.0e8f) {
        fputs("Float32 must be finite and within safe positive range\n", stderr);
        return 2;
    }
    unsigned short caller_cw = 0, active_cw = 0, restored_cw = 0;
    const unsigned short requested_cw = (unsigned short)cw_bits;
    float scaled[4], results[4], fractions[4];
    int steps[4];
    int ok = 1;
    __asm__ volatile("fnstcw %0" : "=m"(caller_cw));
    __asm__ volatile("fldcw %0" :: "m"(requested_cw));
    __asm__ volatile("fnstcw %0" : "=m"(active_cw));
    for (int mode = 0; mode < 4 && ok; ++mode) {
        int factor = (mode == 2 ? 10 : (mode == 3 ? 100 : 1));
        scaled[mode] = store_single_x87((long double)f_range * factor);
        ok = spectrum_graph_default_scale(f_range, mode,
                      &results[mode], &steps[mode], &fractions[mode]);
    }
    __asm__ volatile("fnclex\n\tfldcw %0" :: "m"(caller_cw));
    __asm__ volatile("fnstcw %0" : "=m"(restored_cw));
    if (!ok || (active_cw & (unsigned short)~0x0040u) !=
               (requested_cw & (unsigned short)~0x0040u) ||
        restored_cw != caller_cw) {
        fputs("native x87 replay failed or failed to restore CW\n", stderr);
        return 3;
    }
    printf("# source=STAGE111Z2_NATIVE_X87_REPLAY requested_cw=0x%04X active_cw=0x%04X restored=1\n",
           requested_cw, active_cw);
    for (int mode = 0; mode < 4; ++mode) {
        printf("%d,%08X,%08X,%d,%08X\n", mode,
               (unsigned)single_bits(scaled[mode]),
               (unsigned)single_bits(results[mode]),
               steps[mode], (unsigned)single_bits(fractions[mode]));
    }
    return 0;
}

int main(int argc, char **argv) {
    /* Machine-readable *synthetic-only* selftest: no sensitive values. */
    if (argc == 4 && strcmp(argv[1], "--replay-hex") == 0)
        return run_bitwise_replay(argv[2], argv[3]);

    if(argc!=2 || (strcmp(argv[1],"--selftest")!=0 &&
                   strcmp(argv[1],"--precision-sweep")!=0 &&
                   strcmp(argv[1],"--source-static-cw")!=0)) {
        fputs("usage: x87_graph_vscale_probe --selftest|--precision-sweep|--source-static-cw\n",stderr);
        return 2;
    }
    if(strcmp(argv[1],"--source-static-cw")==0) {
        /* 0x1332 is read from PRIVATE original IDR v3 .data at VA 008C2028.
         * This is on-disk initialization, not verified runtime CW.
         * Execute only fixed synthetic inputs in an isolated child process.
         */
        const unsigned short source_initial_cw=0x1332u;
        unsigned short caller_cw=0, active_cw=0, restored_cw=0;
        const float values[]={0.2f,0.31f,1.0f,2.0f,5.0f,10.0f,20.0f};
        const int modes[]={0,1,2,3};
        __asm__ volatile("fnstcw %0":"=m"(caller_cw));
        __asm__ volatile("fldcw %0"::"m"(source_initial_cw));
        __asm__ volatile("fnstcw %0":"=m"(active_cw));
        float results[28]; int steps[28]; float fractions[28];
        /* Modern CPUs force reserved x87 CW bit 6 to one on readback.
         * It is NOT an IDR content mismatch, and not a precision change.
         */
        int ok=((active_cw & (unsigned short)~0x0040u)==source_initial_cw);
        for(unsigned mode=0;mode<4 && ok;mode++) {
            for(unsigned i=0;i<7 && ok;i++) {
                unsigned idx=7*mode+i;
                ok=spectrum_graph_default_scale(values[i],modes[mode],
                         &results[idx],&steps[idx],&fractions[idx]);
            }
        }
        __asm__ volatile("fnclex\n\tfldcw %0"::"m"(caller_cw));
        __asm__ volatile("fnstcw %0":"=m"(restored_cw));
        if(!ok || restored_cw!=caller_cw) return 3;
        printf("# source=STAGE111W_SYNTHETIC_STATIC_IDR_CW initial=0x%04x active=0x%04x restored=0x%04x\n",
               caller_cw,active_cw,restored_cw);
        for(unsigned mode=0;mode<4;mode++) {
            for(unsigned i=0;i<7;i++) {
                unsigned idx=7*mode+i;
                printf("%.9g,%d,%.9g,%d,%.9g\n",values[i],modes[mode],
                       results[idx],steps[idx],fractions[idx]);
            }
        }
        return 0;
    }
    if(strcmp(argv[1],"--precision-sweep")==0) {
        unsigned short original_cw;
        __asm__ volatile("fnstcw %0":"=m"(original_cw));
        printf("# source=STAGE111V_X87_PRECISION_SWEEP original_cw=0x%04x\n",original_cw);
        const float border[]={0.2f,0.5f,2.0f,5.0f,10.0f,20.0f};
        const unsigned precision[]={0x0000u,0x0200u,0x0300u};
        for(unsigned setting=0;setting<3;setting++) {
            unsigned short cw=(unsigned short)((original_cw & ~0x0300u)|precision[setting]);
            __asm__ volatile("fldcw %0"::"m"(cw));
            for(unsigned row=0;row<sizeof(border)/sizeof(border[0]);row++) {
                float output=0.0f,frac=0.0f;int step=0;
                int ok=spectrum_graph_default_scale(border[row],1,&output,&step,&frac);
                if(!ok) {
                    __asm__ volatile("fldcw %0"::"m"(original_cw));
                    return 3;
                }
                printf("0x%04x,%.9g,%d,%.9g\n",cw,border[row],step,output);
            }
        }
        __asm__ volatile("fldcw %0"::"m"(original_cw));
        return 0;
    }
    const float values[]={0.05f,0.2f,0.5f,1.0f,2.0f,5.0f,10.0f,
        20.0f,50.0f,0.031f,0.31f,0.81f,3.1f,7.1f,12.1f,
        nextafterf(2.0f,0.0f),nextafterf(2.0f,INFINITY),
        nextafterf(5.0f,0.0f),nextafterf(5.0f,INFINITY),
        nextafterf(10.0f,0.0f),nextafterf(10.0f,INFINITY)};
    unsigned short cw=0;
    __asm__ volatile("fnstcw %0":"=m"(cw));
    printf("# source=STAGE111V_SYNTHETIC_X87_HELPER_PROBE x87_control_word=0x%04x\n",cw);
    for(unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++) {
        float output=0.0f,fraction=0.0f;
        int step=0;
        if(!spectrum_graph_default_scale(values[i],1,&output,&step,&fraction))return 3;
        printf("%.9g,%d,%.9g,%d,%.9g\n",values[i],1,output,step,fraction);
    }
    /* Same source arithmetic, independent channel mode factors 1/10/100. */
    const struct {float f_range; int mode;} more[]={
        {0.31f,0},{0.31f,1},{0.31f,2},{0.31f,3},
        {0.031f,2},{0.031f,3}
    };
    for(unsigned i=0;i<sizeof(more)/sizeof(more[0]);i++) {
        float output=0.0f,fraction=0.0f;
        int step=0;
        if(!spectrum_graph_default_scale(more[i].f_range,more[i].mode,
                                          &output,&step,&fraction))return 3;
        printf("%.9g,%d,%.9g,%d,%.9g\n",more[i].f_range,more[i].mode,
               output,step,fraction);
    }
    return 0;
}
