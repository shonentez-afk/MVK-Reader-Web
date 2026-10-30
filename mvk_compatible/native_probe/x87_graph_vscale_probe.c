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

int main(int argc, char **argv) {
    /* Machine-readable *synthetic-only* selftest: no sensitive values. */
    if(argc!=2 || (strcmp(argv[1],"--selftest")!=0 &&
                   strcmp(argv[1],"--precision-sweep")!=0)) {
        fputs("usage: x87_graph_vscale_probe --selftest|--precision-sweep\n",stderr);
        return 2;
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
